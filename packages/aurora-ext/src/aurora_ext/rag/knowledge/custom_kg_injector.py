"""Knowledge-module entry point for custom KG injection.

Wraps :class:`aurora_ext.rag.injection.custom_kg_injector.CustomKGInjector`
with additional support for chunk injection and unified JSON/YAML parsing
with schema validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aurora_ext.rag.injection.custom_kg_injector import (
    CustomKGInjector as _BaseInjector,
)
from aurora_ext.rag.injection.custom_kg_injector import (
    ImportEntity,
    ImportRelationship,
    InjectionStats,
    MergeStrategy,
)
from aurora_ext.rag.storage.base import (
    BaseGraphStorage,
    BaseKVStorage,
    BaseVectorStorage,
)

logger = logging.getLogger(__name__)


# ── Data types ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImportChunk:
    """A text chunk to inject into the knowledge base."""

    chunk_id: str
    content: str
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FullImportData:
    """Parsed import payload containing chunks, entities, and relationships."""

    chunks: list[ImportChunk] = field(default_factory=list)
    entities: list[ImportEntity] = field(default_factory=list)
    relationships: list[ImportRelationship] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            not self.chunks
            and not self.entities
            and not self.relationships
        )


@dataclass
class FullInjectionStats:
    """Extended statistics including chunk injection results."""

    chunks_created: int = 0
    chunks_skipped: int = 0
    entity_stats: InjectionStats = field(default_factory=InjectionStats)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        base = self.entity_stats.to_dict()
        base["chunks_created"] = self.chunks_created
        base["chunks_skipped"] = self.chunks_skipped
        base["errors"] = list(set(self.errors + self.entity_stats.errors))
        return base


# ── Knowledge KG Injector ────────────────────────────────────────────


class KnowledgeKGInjector:
    """Full knowledge graph injector with chunk, entity, and relationship support.

    Parameters
    ----------
    graph_storage:
        Graph storage backend for entities and relationships.
    vector_storage:
        Vector storage for embeddings.
    chunk_kv:
        Optional KV storage for text chunks.
    embedding_func:
        Optional async callable for generating embeddings.
    """

    def __init__(
        self,
        graph_storage: BaseGraphStorage,
        vector_storage: BaseVectorStorage | None = None,
        chunk_kv: BaseKVStorage | None = None,
        embedding_func: Any | None = None,
    ) -> None:
        self._graph = graph_storage
        self._vector = vector_storage
        self._chunk_kv = chunk_kv
        self._embedding_func = embedding_func
        self._base_injector = _BaseInjector(
            graph_storage=graph_storage,
            vector_storage=vector_storage,
            embedding_func=embedding_func,
        )

    async def inject_full(
        self,
        data: FullImportData,
        *,
        strategy: MergeStrategy = MergeStrategy.MERGE,
        kb_name: str = "",
    ) -> FullInjectionStats:
        """Inject chunks, entities, and relationships in a single operation.

        Parameters
        ----------
        data:
            Parsed import data containing chunks, entities, and relationships.
        strategy:
            Conflict resolution strategy.
        kb_name:
            Knowledge base name for multi-KB scoping.
        """
        stats = FullInjectionStats()

        # Phase 1: inject chunks
        if data.chunks and self._chunk_kv is not None:
            await self._inject_chunks(data.chunks, strategy, stats)

        # Phase 2: inject entities and relationships via base injector
        if data.entities or data.relationships:
            entity_stats = await self._base_injector.inject(
                entities=data.entities,
                relationships=data.relationships,
                strategy=strategy,
                kb_name=kb_name,
            )
            stats.entity_stats = entity_stats

        logger.info(
            "Full injection complete for kb=%s: %d chunks created, %d skipped, "
            "%d entities, %d relationships",
            kb_name,
            stats.chunks_created,
            stats.chunks_skipped,
            stats.entity_stats.total_entities,
            stats.entity_stats.total_relationships,
        )

        return stats

    async def _inject_chunks(
        self,
        chunks: list[ImportChunk],
        strategy: MergeStrategy,
        stats: FullInjectionStats,
    ) -> None:
        """Batch-inject chunks into the KV storage."""
        assert self._chunk_kv is not None

        # Batch-fetch existing chunk IDs to avoid N+1
        existing_keys = set(await self._chunk_kv.all_keys())

        batch: dict[str, dict[str, Any]] = {}

        for chunk in chunks:
            try:
                if chunk.chunk_id in existing_keys:
                    if strategy == MergeStrategy.SKIP:
                        stats.chunks_skipped += 1
                        continue
                    if strategy == MergeStrategy.MERGE:
                        existing = await self._chunk_kv.get_by_id(chunk.chunk_id)
                        if existing:
                            merged_content = (
                                f"{existing.get('content', '')}\n{chunk.content}"
                            )
                            chunk_data = {
                                **existing,
                                "content": merged_content,
                                "source_id": chunk.source_id
                                or existing.get("source_id", ""),
                            }
                            batch[chunk.chunk_id] = chunk_data
                            stats.chunks_created += 1
                            continue

                # New chunk or overwrite
                chunk_data: dict[str, Any] = {
                    "content": chunk.content,
                    "source_id": chunk.source_id,
                    "full_doc_id": chunk.source_id,
                }
                if chunk.metadata:
                    for k, v in chunk.metadata.items():
                        if isinstance(v, (list, dict)):
                            chunk_data[k] = str(v)
                        else:
                            chunk_data[k] = v

                batch[chunk.chunk_id] = chunk_data
                stats.chunks_created += 1

            except Exception as exc:
                msg = f"Chunk '{chunk.chunk_id}': {exc}"
                logger.warning("Failed to prepare chunk: %s", msg)
                stats.errors.append(msg)

        if batch:
            try:
                await self._chunk_kv.upsert(batch)
            except Exception as exc:
                msg = f"Batch chunk upsert failed: {exc}"
                logger.error(msg)
                stats.errors.append(msg)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def parse_import_data(raw: dict[str, Any]) -> FullImportData:
        """Parse a raw dict (from JSON or YAML) into FullImportData.

        Expected structure::

            {
                "chunks": [...],
                "entities": [...],
                "relationships": [...]
            }
        """
        chunks = KnowledgeKGInjector.parse_chunks(raw.get("chunks", []))
        entities = _BaseInjector.parse_entities_from_dict(
            raw.get("entities", [])
        )
        relationships = _BaseInjector.parse_relationships_from_dict(
            raw.get("relationships", [])
        )
        return FullImportData(
            chunks=chunks,
            entities=entities,
            relationships=relationships,
        )

    @staticmethod
    def parse_chunks(raw_chunks: list[dict[str, Any]]) -> list[ImportChunk]:
        """Parse a list of raw dicts into ImportChunk instances."""
        chunks: list[ImportChunk] = []
        for raw in raw_chunks:
            chunk_id = raw.get("chunk_id") or raw.get("id", "")
            content = raw.get("content", "")
            if not chunk_id or not content:
                continue
            chunks.append(
                ImportChunk(
                    chunk_id=chunk_id,
                    content=content,
                    source_id=raw.get("source_id", raw.get("source", "")),
                    metadata=raw.get("metadata", {}),
                )
            )
        return chunks

    @staticmethod
    def parse_yaml_content(yaml_content: str) -> dict[str, Any]:
        """Parse YAML content into a raw import dict.

        Raises
        ------
        ImportError
            If PyYAML is not installed.
        ValueError
            If the YAML content is invalid.
        """
        return _BaseInjector.parse_from_yaml(yaml_content)
