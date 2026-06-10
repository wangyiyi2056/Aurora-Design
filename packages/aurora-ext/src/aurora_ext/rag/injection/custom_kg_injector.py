"""Batch injection of custom entities and relationships into the knowledge graph.

Supports JSON and YAML input, automatic embedding generation, and configurable
merge strategies (overwrite / merge / skip) for conflict resolution.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

from aurora_ext.rag.storage.base import BaseGraphStorage, BaseVectorStorage

logger = logging.getLogger(__name__)

GRAPH_FIELD_SEP = "<SEP>"

# Maximum texts per embedding batch to stay within model limits
_EMBEDDING_BATCH_SIZE = 64


# ── Types ────────────────────────────────────────────────────────────


class MergeStrategy(str, enum.Enum):
    """Conflict resolution strategy for existing entities/relationships."""

    OVERWRITE = "overwrite"
    MERGE = "merge"
    SKIP = "skip"


@dataclass(frozen=True)
class ImportEntity:
    """A single entity to inject into the knowledge graph."""

    entity_name: str
    entity_type: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportRelationship:
    """A single relationship to inject into the knowledge graph."""

    source_entity: str
    target_entity: str
    description: str = ""
    keywords: str = ""
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InjectionStats:
    """Statistics returned after a batch injection operation."""

    entities_created: int = 0
    entities_updated: int = 0
    entities_skipped: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    relationships_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_entities(self) -> int:
        return self.entities_created + self.entities_updated + self.entities_skipped

    @property
    def total_relationships(self) -> int:
        return (
            self.relationships_created
            + self.relationships_updated
            + self.relationships_skipped
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "entities_skipped": self.entities_skipped,
            "relationships_created": self.relationships_created,
            "relationships_updated": self.relationships_updated,
            "relationships_skipped": self.relationships_skipped,
            "errors": self.errors,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
        }


# ── Injector ─────────────────────────────────────────────────────────


class CustomKGInjector:
    """Batch-inject entities and relationships into the knowledge graph.

    Parameters
    ----------
    graph_storage:
        The graph storage backend to write nodes/edges into.
    vector_storage:
        The vector storage backend for entity embeddings.
        May be ``None`` if embedding generation is not required.
    embedding_func:
        An async callable ``(texts, is_query) -> embeddings`` that
        produces vector representations.  May be ``None``.
    """

    def __init__(
        self,
        graph_storage: BaseGraphStorage,
        vector_storage: BaseVectorStorage | None = None,
        embedding_func: Any | None = None,
    ) -> None:
        self._graph = graph_storage
        self._vector = vector_storage
        self._embedding_func = embedding_func

    # ── Public API ───────────────────────────────────────────────────

    async def inject(
        self,
        entities: list[ImportEntity],
        relationships: list[ImportRelationship],
        *,
        strategy: MergeStrategy = MergeStrategy.MERGE,
        kb_name: str = "",
    ) -> InjectionStats:
        """Batch-inject entities and relationships.

        Parameters
        ----------
        entities:
            Entities to inject.
        relationships:
            Relationships to inject.  Source and target entities are
            auto-created if they do not already exist.
        strategy:
            How to handle conflicts with existing nodes/edges.
        kb_name:
            Knowledge base name (reserved for multi-KB scoping).

        Returns
        -------
        InjectionStats
            Counts of created, updated, and skipped records plus errors.
        """
        stats = InjectionStats()

        # Phase 1: batch-fetch existing nodes to avoid N+1 lookups
        existing_nodes = await self._batch_get_nodes(
            [e.entity_name for e in entities]
            + [r.source_entity for r in relationships]
            + [r.target_entity for r in relationships]
        )

        # Phase 2: inject entities
        await self._inject_entities(entities, existing_nodes, strategy, stats)

        # Phase 3: inject relationships (auto-create missing endpoints)
        await self._inject_relationships(
            relationships, existing_nodes, strategy, stats
        )

        # Phase 4: generate embeddings for new/updated entities
        await self._generate_entity_embeddings(entities, existing_nodes, strategy)

        logger.info(
            "Injection complete for kb=%s: %d entities (created=%d updated=%d "
            "skipped=%d), %d relationships (created=%d updated=%d skipped=%d), "
            "%d errors",
            kb_name,
            stats.total_entities,
            stats.entities_created,
            stats.entities_updated,
            stats.entities_skipped,
            stats.total_relationships,
            stats.relationships_created,
            stats.relationships_updated,
            stats.relationships_skipped,
            len(stats.errors),
        )

        return stats

    # ── Batch node fetch ─────────────────────────────────────────────

    async def _batch_get_nodes(
        self, node_ids: list[str]
    ) -> dict[str, dict[str, Any] | None]:
        """Fetch multiple nodes in a single pass, avoiding N+1 queries.

        Returns a dict mapping each node_id to its data (or ``None``).
        """
        unique_ids = list(set(node_ids))
        result: dict[str, dict[str, Any] | None] = {}

        for node_id in unique_ids:
            result[node_id] = await self._graph.get_node(node_id)

        return result

    # ── Entity injection ─────────────────────────────────────────────

    async def _inject_entities(
        self,
        entities: list[ImportEntity],
        existing_nodes: dict[str, dict[str, Any] | None],
        strategy: MergeStrategy,
        stats: InjectionStats,
    ) -> None:
        """Inject entities into graph storage with the chosen merge strategy."""
        for entity in entities:
            try:
                existing = existing_nodes.get(entity.entity_name)

                if existing is not None:
                    if strategy == MergeStrategy.SKIP:
                        stats.entities_skipped += 1
                        continue

                    if strategy == MergeStrategy.OVERWRITE:
                        node_data = self._build_node_data(entity)
                        await self._graph.upsert_node(entity.entity_name, node_data)
                        stats.entities_updated += 1
                        continue

                    # Merge strategy: combine descriptions and metadata
                    merged_data = self._merge_entity_data(existing, entity)
                    await self._graph.upsert_node(entity.entity_name, merged_data)
                    stats.entities_updated += 1
                else:
                    node_data = self._build_node_data(entity)
                    await self._graph.upsert_node(entity.entity_name, node_data)
                    existing_nodes[entity.entity_name] = node_data
                    stats.entities_created += 1

            except Exception as exc:
                msg = f"Entity '{entity.entity_name}': {exc}"
                logger.warning("Failed to inject entity: %s", msg)
                stats.errors.append(msg)

    def _build_node_data(self, entity: ImportEntity) -> dict[str, Any]:
        """Build a graph node dict from an ImportEntity."""
        data: dict[str, Any] = {
            "entity_name": entity.entity_name,
            "entity_type": entity.entity_type,
            "description": entity.description,
            "source_id": "custom_import",
            "weight": 1.0,
        }
        if entity.metadata:
            for k, v in entity.metadata.items():
                if isinstance(v, (list, dict)):
                    data[k] = str(v)
                else:
                    data[k] = v
        return data

    def _merge_entity_data(
        self, existing: dict[str, Any], entity: ImportEntity
    ) -> dict[str, Any]:
        """Merge new entity data into existing node data."""
        merged = dict(existing)

        # Merge description (append unique segments)
        old_desc = existing.get("description", "")
        new_desc = entity.description
        if new_desc:
            existing_parts = {
                p.strip() for p in old_desc.split(GRAPH_FIELD_SEP) if p.strip()
            }
            for part in new_desc.split(GRAPH_FIELD_SEP):
                stripped = part.strip()
                if stripped and stripped not in existing_parts:
                    old_desc = f"{old_desc}{GRAPH_FIELD_SEP}{stripped}" if old_desc else stripped
            merged["description"] = old_desc

        # Merge source_id
        old_src = existing.get("source_id", "")
        if "custom_import" not in old_src:
            merged["source_id"] = (
                f"{old_src}{GRAPH_FIELD_SEP}custom_import" if old_src else "custom_import"
            )

        # Update entity_type if previously empty
        if entity.entity_type and not existing.get("entity_type"):
            merged["entity_type"] = entity.entity_type

        # Increment weight
        merged["weight"] = float(existing.get("weight", 1.0)) + 1.0

        # Merge custom metadata
        if entity.metadata:
            for k, v in entity.metadata.items():
                safe_v = str(v) if isinstance(v, (list, dict)) else v
                merged[k] = safe_v

        return merged

    # ── Relationship injection ───────────────────────────────────────

    async def _inject_relationships(
        self,
        relationships: list[ImportRelationship],
        existing_nodes: dict[str, dict[str, Any] | None],
        strategy: MergeStrategy,
        stats: InjectionStats,
    ) -> None:
        """Inject relationships, auto-creating missing endpoint entities."""
        for rel in relationships:
            try:
                # Auto-create source entity if missing
                if existing_nodes.get(rel.source_entity) is None:
                    auto_data = {
                        "entity_name": rel.source_entity,
                        "entity_type": "",
                        "description": "",
                        "source_id": "custom_import",
                        "weight": 1.0,
                    }
                    await self._graph.upsert_node(rel.source_entity, auto_data)
                    existing_nodes[rel.source_entity] = auto_data
                    stats.entities_created += 1

                # Auto-create target entity if missing
                if existing_nodes.get(rel.target_entity) is None:
                    auto_data = {
                        "entity_name": rel.target_entity,
                        "entity_type": "",
                        "description": "",
                        "source_id": "custom_import",
                        "weight": 1.0,
                    }
                    await self._graph.upsert_node(rel.target_entity, auto_data)
                    existing_nodes[rel.target_entity] = auto_data
                    stats.entities_created += 1

                # Check if edge already exists
                existing_edge = await self._graph.get_edge(
                    rel.source_entity, rel.target_entity
                )

                if existing_edge is not None:
                    if strategy == MergeStrategy.SKIP:
                        stats.relationships_skipped += 1
                        continue

                    if strategy == MergeStrategy.OVERWRITE:
                        edge_data = self._build_edge_data(rel)
                        await self._graph.upsert_edge(
                            rel.source_entity, rel.target_entity, edge_data
                        )
                        stats.relationships_updated += 1
                        continue

                    # Merge strategy
                    merged_edge = self._merge_edge_data(existing_edge, rel)
                    await self._graph.upsert_edge(
                        rel.source_entity, rel.target_entity, merged_edge
                    )
                    stats.relationships_updated += 1
                else:
                    edge_data = self._build_edge_data(rel)
                    await self._graph.upsert_edge(
                        rel.source_entity, rel.target_entity, edge_data
                    )
                    stats.relationships_created += 1

            except Exception as exc:
                msg = (
                    f"Relationship '{rel.source_entity}' -> "
                    f"'{rel.target_entity}': {exc}"
                )
                logger.warning("Failed to inject relationship: %s", msg)
                stats.errors.append(msg)

    def _build_edge_data(self, rel: ImportRelationship) -> dict[str, Any]:
        """Build a graph edge dict from an ImportRelationship."""
        data: dict[str, Any] = {
            "src_id": rel.source_entity,
            "tgt_id": rel.target_entity,
            "description": rel.description,
            "keywords": rel.keywords,
            "source_id": "custom_import",
            "weight": rel.weight,
        }
        if rel.metadata:
            for k, v in rel.metadata.items():
                if isinstance(v, (list, dict)):
                    data[k] = str(v)
                else:
                    data[k] = v
        return data

    def _merge_edge_data(
        self, existing: dict[str, Any], rel: ImportRelationship
    ) -> dict[str, Any]:
        """Merge new relationship data into existing edge data."""
        merged = dict(existing)

        # Merge description
        old_desc = existing.get("description", "")
        if rel.description:
            existing_parts = {
                p.strip() for p in old_desc.split(GRAPH_FIELD_SEP) if p.strip()
            }
            for part in rel.description.split(GRAPH_FIELD_SEP):
                stripped = part.strip()
                if stripped and stripped not in existing_parts:
                    old_desc = f"{old_desc}{GRAPH_FIELD_SEP}{stripped}" if old_desc else stripped
            merged["description"] = old_desc

        # Merge keywords
        old_kw = existing.get("keywords", "")
        if rel.keywords and rel.keywords not in old_kw:
            merged["keywords"] = f"{old_kw},{rel.keywords}" if old_kw else rel.keywords

        # Merge source_id
        old_src = existing.get("source_id", "")
        if "custom_import" not in old_src:
            merged["source_id"] = (
                f"{old_src}{GRAPH_FIELD_SEP}custom_import" if old_src else "custom_import"
            )

        # Accumulate weight
        merged["weight"] = float(existing.get("weight", 1.0)) + rel.weight

        # Merge custom metadata
        if rel.metadata:
            for k, v in rel.metadata.items():
                safe_v = str(v) if isinstance(v, (list, dict)) else v
                merged[k] = safe_v

        return merged

    # ── Embedding generation ─────────────────────────────────────────

    async def _generate_entity_embeddings(
        self,
        entities: list[ImportEntity],
        existing_nodes: dict[str, dict[str, Any] | None],
        strategy: MergeStrategy,
    ) -> None:
        """Generate and store embeddings for newly created or updated entities.

        Skipped entities (via ``MergeStrategy.SKIP``) are not re-embedded.
        """
        if self._embedding_func is None or self._vector is None:
            return

        # Collect texts for entities that need embedding
        texts_to_embed: list[str] = []
        entity_names: list[str] = []

        for entity in entities:
            existing = existing_nodes.get(entity.entity_name)
            was_existing_before = existing is not None

            if was_existing_before and strategy == MergeStrategy.SKIP:
                continue

            # Build the embedding text from the entity's final state
            node = existing_nodes.get(entity.entity_name) or {}
            desc = node.get("description", entity.description) or entity.description
            text = f"{entity.entity_name}: {desc[:500]}"
            texts_to_embed.append(text)
            entity_names.append(entity.entity_name)

        if not texts_to_embed:
            return

        # Batch embedding in chunks to respect model limits
        for batch_start in range(0, len(texts_to_embed), _EMBEDDING_BATCH_SIZE):
            batch_end = min(batch_start + _EMBEDDING_BATCH_SIZE, len(texts_to_embed))
            batch_texts = texts_to_embed[batch_start:batch_end]
            batch_names = entity_names[batch_start:batch_end]

            try:
                embeddings = await self._embedding_func(
                    batch_texts, is_query=False
                )

                vector_data: dict[str, dict[str, Any]] = {}
                for i, name in enumerate(batch_names):
                    node = existing_nodes.get(name) or {}
                    vector_data[name] = {
                        "content": batch_texts[i],
                        "__vector__": embeddings[i].tolist(),
                        "entity_name": name,
                        "entity_type": node.get("entity_type", ""),
                        "description": node.get("description", ""),
                    }

                await self._vector.upsert(vector_data)

            except Exception as exc:
                logger.warning(
                    "Failed to generate embeddings for batch %d-%d: %s",
                    batch_start,
                    batch_end,
                    exc,
                )

    # ── Input parsing helpers ────────────────────────────────────────

    @staticmethod
    def parse_entities_from_dict(
        raw_entities: list[dict[str, Any]],
    ) -> list[ImportEntity]:
        """Parse a list of raw dicts into ImportEntity instances."""
        entities: list[ImportEntity] = []
        for raw in raw_entities:
            name = raw.get("entity_name") or raw.get("name", "")
            if not name:
                continue
            entities.append(
                ImportEntity(
                    entity_name=name,
                    entity_type=raw.get("entity_type", raw.get("type", "")),
                    description=raw.get("description", ""),
                    metadata=raw.get("metadata", {}),
                )
            )
        return entities

    @staticmethod
    def parse_relationships_from_dict(
        raw_relationships: list[dict[str, Any]],
    ) -> list[ImportRelationship]:
        """Parse a list of raw dicts into ImportRelationship instances."""
        relationships: list[ImportRelationship] = []
        for raw in raw_relationships:
            source = raw.get("source_entity") or raw.get("source", "")
            target = raw.get("target_entity") or raw.get("target", "")
            if not source or not target:
                continue
            relationships.append(
                ImportRelationship(
                    source_entity=source,
                    target_entity=target,
                    description=raw.get("description", ""),
                    keywords=raw.get("keywords", ""),
                    weight=float(raw.get("weight", 1.0)),
                    metadata=raw.get("metadata", {}),
                )
            )
        return relationships

    @staticmethod
    def parse_from_yaml(yaml_content: str) -> dict[str, Any]:
        """Parse YAML content into the import payload structure.

        Returns a dict with ``entities``, ``relationships``, and
        ``merge_strategy`` keys.

        Raises
        ------
        ImportError
            If PyYAML is not installed.
        ValueError
            If the YAML content is invalid or not a mapping.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for YAML import. "
                "Install it with: pip install pyyaml"
            ) from exc

        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            raise ValueError("YAML content must be a mapping/dict")
        return data
