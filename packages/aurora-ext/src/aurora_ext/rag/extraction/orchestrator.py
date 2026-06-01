"""Extraction orchestrator — batch concurrent entity/relationship extraction.

The :class:`ExtractionOrchestrator` coordinates multi-chunk extraction
workloads with semaphore-based concurrency control, incremental change
detection, and per-chunk error isolation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from aurora_ext.rag.extraction.config import (
    AddonParams,
    ExtractionConfig,
    EntityTypeConfig,
    KGExtractionFullConfig,
)
from aurora_ext.rag.extraction.extractor import EntityRelationExtractor
from aurora_ext.rag.extraction.types import ExtractionResult

logger = logging.getLogger(__name__)


# ── Batch result types ───────────────────────────────────────────────


@dataclass(frozen=True)
class BatchExtractionStats:
    """Summary statistics for a batch extraction run."""

    total_chunks: int = 0
    successful_chunks: int = 0
    failed_chunks: int = 0
    skipped_chunks: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class BatchExtractionResult:
    """Aggregate result of a batch extraction run."""

    results: list[ExtractionResult] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    stats: BatchExtractionStats = field(default_factory=BatchExtractionStats)


# ── Chunk identity for incremental extraction ────────────────────────

# A chunk is identified by ``(chunk_id, content_hash)``.  If the
# orchestrator's ``processed_chunks`` set already contains the pair,
# the chunk is skipped during incremental extraction.


# ── Orchestrator ─────────────────────────────────────────────────────


class ExtractionOrchestrator:
    """Concurrent batch orchestrator for knowledge graph extraction.

    Wraps an :class:`EntityRelationExtractor` and processes multiple
    text chunks concurrently, bounded by an asyncio semaphore.

    Parameters
    ----------
    extractor:
        The underlying entity/relationship extractor.
    config:
        Extraction pipeline configuration.  When ``None`` sensible
        defaults are used.
    entity_type_config:
        Entity / relation type customisation.
    addon:
        Supplementary parameters (language, guidance overrides).
    processed_chunks:
        Optional set of ``(chunk_id, content_hash)`` tuples that have
        already been processed.  Used for incremental extraction.
    """

    def __init__(
        self,
        extractor: EntityRelationExtractor,
        *,
        config: ExtractionConfig | None = None,
        entity_type_config: EntityTypeConfig | None = None,
        addon: AddonParams | None = None,
        processed_chunks: set[tuple[str, str]] | None = None,
    ) -> None:
        self._extractor = extractor
        self._config = config or ExtractionConfig()
        self._entity_type_config = entity_type_config or EntityTypeConfig()
        self._addon = addon or AddonParams()
        self._semaphore = asyncio.Semaphore(self._config.max_parallel_extract)
        self._processed_chunks: set[tuple[str, str]] = processed_chunks or set()

    @classmethod
    def from_full_config(
        cls,
        extractor: EntityRelationExtractor,
        full_config: KGExtractionFullConfig,
        *,
        processed_chunks: set[tuple[str, str]] | None = None,
    ) -> ExtractionOrchestrator:
        """Construct from a :class:`KGExtractionFullConfig`."""
        return cls(
            extractor,
            config=full_config.extraction,
            entity_type_config=full_config.entity_types,
            addon=full_config.addon,
            processed_chunks=processed_chunks,
        )

    # ── Properties ─────────────────────────────────────────────────

    @property
    def config(self) -> ExtractionConfig:
        return self._config

    @property
    def entity_type_config(self) -> EntityTypeConfig:
        return self._entity_type_config

    @property
    def addon(self) -> AddonParams:
        return self._addon

    @property
    def processed_chunk_count(self) -> int:
        return len(self._processed_chunks)

    # ── Public API ─────────────────────────────────────────────────

    async def extract_single(
        self,
        text: str,
        chunk_id: str,
        file_path: str = "",
        content_hash: str = "",
    ) -> ExtractionResult:
        """Extract entities and relationships from a single text chunk.

        Respects the concurrency semaphore and incremental skip logic.

        Parameters
        ----------
        text:
            Raw chunk text.
        chunk_id:
            Unique chunk identifier.
        file_path:
            Source file path for provenance.
        content_hash:
            Hash of the chunk content for incremental detection.

        Returns
        -------
        ExtractionResult
            The extraction output.  If skipped (incremental mode),
            returns an empty result.
        """
        # Incremental skip check.
        if self._config.enable_incremental_extract and content_hash:
            key = (chunk_id, content_hash)
            if key in self._processed_chunks:
                logger.debug("Skipping already-processed chunk %s", chunk_id)
                return ExtractionResult(chunk_id=chunk_id)

        async with self._semaphore:
            result = await self._extractor.extract(
                chunk_text=text,
                chunk_id=chunk_id,
                file_path=file_path,
                **self._build_extract_kwargs(),
            )

        # Mark as processed.
        if content_hash:
            self._processed_chunks.add((chunk_id, content_hash))

        return result

    async def extract_batch(
        self,
        chunks: list[dict[str, str]],
        *,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> BatchExtractionResult:
        """Extract entities and relationships from a batch of text chunks.

        Chunks are processed concurrently up to ``max_parallel_extract``.
        Individual chunk failures are captured in ``errors`` without
        aborting the entire batch.

        Parameters
        ----------
        chunks:
            List of dicts, each with keys ``text``, ``chunk_id``, and
            optionally ``file_path`` and ``content_hash``.
        on_progress:
            Optional async callback ``(completed, total)`` invoked after
            each chunk finishes.

        Returns
        -------
        BatchExtractionResult
            Aggregated results, errors, and statistics.
        """
        if not chunks:
            return BatchExtractionResult(
                stats=BatchExtractionStats(elapsed_seconds=0.0)
            )

        total = len(chunks)
        completed = 0
        results: list[ExtractionResult] = []
        errors: list[dict[str, Any]] = []
        skipped = 0
        total_entities = 0
        total_relationships = 0

        start_time = time.monotonic()

        async def _process_one(chunk: dict[str, str]) -> None:
            nonlocal completed, skipped, total_entities, total_relationships

            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            file_path = chunk.get("file_path", "")
            content_hash = chunk.get("content_hash", "")

            try:
                result = await self.extract_single(
                    text=text,
                    chunk_id=chunk_id,
                    file_path=file_path,
                    content_hash=content_hash,
                )

                if not result.entities and not result.relationships:
                    # Could be an incremental skip or genuinely empty.
                    if self._config.enable_incremental_extract and content_hash:
                        key = (chunk_id, content_hash)
                        if key in self._processed_chunks:
                            skipped += 1

                results.append(result)
                total_entities += len(result.entities)
                total_relationships += len(result.relationships)

            except Exception as exc:
                logger.error(
                    "Extraction failed for chunk %s: %s", chunk_id, exc
                )
                errors.append({
                    "chunk_id": chunk_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })

            completed += 1
            if on_progress is not None:
                await on_progress(completed, total)

        tasks = [asyncio.create_task(_process_one(c)) for c in chunks]
        await asyncio.gather(*tasks)

        elapsed = time.monotonic() - start_time
        successful = total - len(errors) - skipped

        stats = BatchExtractionStats(
            total_chunks=total,
            successful_chunks=successful,
            failed_chunks=len(errors),
            skipped_chunks=skipped,
            total_entities=total_entities,
            total_relationships=total_relationships,
            elapsed_seconds=round(elapsed, 3),
        )

        logger.info(
            "Batch extraction complete: %d/%d chunks, %d entities, "
            "%d relationships in %.2fs",
            successful,
            total,
            total_entities,
            total_relationships,
            elapsed,
        )

        return BatchExtractionResult(results=results, errors=errors, stats=stats)

    # ── Helpers ────────────────────────────────────────────────────

    def _build_extract_kwargs(self) -> dict[str, Any]:
        """Build the ``**config`` kwargs forwarded to ``EntityRelationExtractor.extract``."""
        # Resolve entity types guidance.
        entity_guidance = self._addon.entity_types_guidance
        if entity_guidance is None:
            entity_guidance = self._entity_type_config.build_entity_types_guidance()

        return {
            "language": self._addon.language,
            "max_total_records": self._config.max_total_records,
            "max_entity_records": self._config.max_entity_records,
            "use_json": self._config.use_json,
            "max_gleaning": self._config.max_gleaning,
            "entity_extract_max_gleaning": self._config.entity_extract_max_gleaning,
            "relation_extract_max_gleaning": self._config.relation_extract_max_gleaning,
            "entity_types_guidance": entity_guidance,
            "relation_types_guidance": self._addon.relation_types_guidance
            or self._entity_type_config.build_relation_types_guidance(),
            "enable_cache": self._config.enable_cache,
        }
