"""Advanced knowledge graph management operations.

Provides entity merge with configurable strategies, complementing the
basic CRUD operations already available on :class:`BaseGraphStorage`.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

from aurora_ext.rag.storage.base import BaseGraphStorage, BaseVectorStorage

logger = logging.getLogger(__name__)

GRAPH_FIELD_SEP = "<SEP>"


# ── Merge strategies ─────────────────────────────────────────────────


class MergeStrategy(str, enum.Enum):
    """Strategy for combining property values during entity merge.

    - ``CONCATENATE`` — join all values with the field separator.
    - ``KEEP_FIRST``  — keep the target entity's value, discard others.
    - ``JOIN_UNIQUE`` — join only values not already present.
    """

    CONCATENATE = "concatenate"
    KEEP_FIRST = "keep_first"
    JOIN_UNIQUE = "join_unique"


# ── Result types ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class MergeResult:
    """Outcome of an entity merge operation."""

    target_entity: str
    merged_count: int
    deleted_entities: list[str] = field(default_factory=list)
    migrated_edges: int = 0
    skipped_entities: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_entity": self.target_entity,
            "merged_count": self.merged_count,
            "deleted_entities": list(self.deleted_entities),
            "migrated_edges": self.migrated_edges,
            "skipped_entities": list(self.skipped_entities),
            "errors": list(self.errors),
            "success": self.success,
        }


# ── Graph Manager ────────────────────────────────────────────────────


class GraphManager:
    """High-level knowledge graph management operations.

    Parameters
    ----------
    graph_storage:
        The graph storage backend for node/edge operations.
    vector_storage:
        Optional vector storage for updating embeddings after merge.
    embedding_func:
        Optional async callable ``(texts, is_query) -> embeddings``.
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

    # ── Entity merge ──────────────────────────────────────────────

    async def merge_entities(
        self,
        target_entity: str,
        source_entities: list[str],
        *,
        strategy: MergeStrategy = MergeStrategy.JOIN_UNIQUE,
    ) -> MergeResult:
        """Merge multiple source entities into the target entity.

        All edges from source entities are re-wired to the target.
        Source entities are deleted after merging.

        Parameters
        ----------
        target_entity:
            The entity name to merge into (must already exist).
        source_entities:
            Entity names to merge away (deleted after merge).
        strategy:
            How to combine property values (description, source_id, etc.).

        Returns
        -------
        MergeResult
            Statistics about the merge operation.
        """
        # Validate target exists
        if not await self._graph.has_node(target_entity):
            raise ValueError(
                f"Target entity '{target_entity}' does not exist"
            )

        target_data = await self._graph.get_node(target_entity) or {}
        deleted: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        migrated_edges = 0

        for entity_name in source_entities:
            if entity_name == target_entity:
                continue

            if not await self._graph.has_node(entity_name):
                logger.warning(
                    "Skipping merge source '%s': not found", entity_name
                )
                skipped.append(entity_name)
                continue

            try:
                migrated = await self._merge_single_entity(
                    target_entity, target_data, entity_name, strategy
                )
                migrated_edges += migrated
                deleted.append(entity_name)
            except Exception as exc:
                msg = f"Failed to merge '{entity_name}': {exc}"
                logger.error(msg)
                errors.append(msg)

        # Write back the merged target data
        await self._graph.upsert_node(target_entity, target_data)

        # Update vector embeddings for the merged entity
        await self._update_entity_embedding(target_entity, target_data)

        return MergeResult(
            target_entity=target_entity,
            merged_count=len(deleted),
            deleted_entities=deleted,
            migrated_edges=migrated_edges,
            skipped_entities=skipped,
            errors=errors,
        )

    async def _merge_single_entity(
        self,
        target_name: str,
        target_data: dict[str, Any],
        source_name: str,
        strategy: MergeStrategy,
    ) -> int:
        """Merge one source entity into the target, re-wiring edges.

        Returns the number of edges migrated.
        """
        src_data = await self._graph.get_node(source_name) or {}
        migrated_edges = 0

        # Merge properties into the target
        self._merge_properties(target_data, src_data, strategy)

        # Re-wire all edges from source to target
        edges = await self._graph.get_node_edges(source_name)
        for src, tgt in edges:
            edge_data = await self._graph.get_edge(src, tgt)

            new_src = target_name if src == source_name else src
            new_tgt = target_name if tgt == source_name else tgt

            # Skip self-loops after merge
            if new_src == new_tgt:
                await self._graph.delete_edge(src, tgt)
                continue

            if not await self._graph.has_edge(new_src, new_tgt):
                if edge_data:
                    await self._graph.upsert_edge(new_src, new_tgt, edge_data)
                    migrated_edges += 1
            else:
                # Edge already exists — merge edge descriptions
                existing_edge = await self._graph.get_edge(new_src, new_tgt)
                if existing_edge and edge_data:
                    merged_edge = self._merge_edge_properties(
                        existing_edge, edge_data, strategy
                    )
                    await self._graph.upsert_edge(new_src, new_tgt, merged_edge)
                    migrated_edges += 1

            await self._graph.delete_edge(src, tgt)

        # Delete the source entity
        await self._graph.delete_node(source_name)

        return migrated_edges

    # Fields that should not be merged via string concatenation
    _SKIP_MERGE_KEYS = frozenset({"id", "entity_name", "weight"})

    def _merge_properties(
        self,
        target: dict[str, Any],
        source: dict[str, Any],
        strategy: MergeStrategy,
    ) -> None:
        """Merge source properties into target using the given strategy."""
        for key, src_value in source.items():
            if key in self._SKIP_MERGE_KEYS:
                continue

            tgt_value = target.get(key, "")

            if strategy == MergeStrategy.KEEP_FIRST:
                # Keep target value; only fill if target is empty
                if not tgt_value and src_value:
                    target[key] = src_value

            elif strategy == MergeStrategy.CONCATENATE:
                # Always concatenate
                if src_value:
                    if tgt_value:
                        target[key] = f"{tgt_value}{GRAPH_FIELD_SEP}{src_value}"
                    else:
                        target[key] = src_value

            elif strategy == MergeStrategy.JOIN_UNIQUE:
                # Only add if not already present
                if src_value:
                    existing_parts = {
                        p.strip()
                        for p in str(tgt_value).split(GRAPH_FIELD_SEP)
                        if p.strip()
                    }
                    new_parts = [
                        p.strip()
                        for p in str(src_value).split(GRAPH_FIELD_SEP)
                        if p.strip() and p.strip() not in existing_parts
                    ]
                    if new_parts:
                        joined = GRAPH_FIELD_SEP.join(new_parts)
                        if tgt_value:
                            target[key] = f"{tgt_value}{GRAPH_FIELD_SEP}{joined}"
                        else:
                            target[key] = joined

        # Always bump weight on merge
        target["weight"] = float(target.get("weight", 1.0)) + float(
            source.get("weight", 1.0)
        )

    def _merge_edge_properties(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        strategy: MergeStrategy,
    ) -> dict[str, Any]:
        """Merge incoming edge data into an existing edge."""
        merged = dict(existing)

        for key in ("description", "keywords", "source_id"):
            src_val = incoming.get(key, "")
            tgt_val = merged.get(key, "")

            if not src_val:
                continue

            if strategy == MergeStrategy.KEEP_FIRST:
                continue

            if strategy == MergeStrategy.CONCATENATE:
                merged[key] = (
                    f"{tgt_val}{GRAPH_FIELD_SEP}{src_val}" if tgt_val else src_val
                )

            elif strategy == MergeStrategy.JOIN_UNIQUE:
                existing_parts = {
                    p.strip() for p in str(tgt_val).split(GRAPH_FIELD_SEP) if p.strip()
                }
                new_parts = [
                    p.strip()
                    for p in str(src_val).split(GRAPH_FIELD_SEP)
                    if p.strip() and p.strip() not in existing_parts
                ]
                if new_parts:
                    joined = GRAPH_FIELD_SEP.join(new_parts)
                    merged[key] = (
                        f"{tgt_val}{GRAPH_FIELD_SEP}{joined}" if tgt_val else joined
                    )

        merged["weight"] = float(merged.get("weight", 1.0)) + float(
            incoming.get("weight", 1.0)
        )
        return merged

    async def _update_entity_embedding(
        self,
        entity_name: str,
        node_data: dict[str, Any],
    ) -> None:
        """Regenerate the embedding for a merged entity."""
        if self._embedding_func is None or self._vector is None:
            return

        desc = node_data.get("description", "")
        text = f"{entity_name}: {desc[:500]}"

        try:
            embeddings = await self._embedding_func([text], is_query=False)
            vector_data = {
                entity_name: {
                    "content": text,
                    "__vector__": embeddings[0].tolist(),
                    "entity_name": entity_name,
                    "entity_type": node_data.get("entity_type", ""),
                    "description": desc,
                }
            }
            await self._vector.upsert(vector_data)
        except Exception as exc:
            logger.warning(
                "Failed to update embedding for merged entity '%s': %s",
                entity_name,
                exc,
            )
