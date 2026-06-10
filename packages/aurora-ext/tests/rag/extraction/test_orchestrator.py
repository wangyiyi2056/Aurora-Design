"""Tests for the ExtractionOrchestrator.

Covers concurrency control, batch extraction, incremental skip,
error isolation, and progress reporting.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aurora_ext.rag.extraction.config import (
    AddonParams,
    ExtractionConfig,
    EntityTypeConfig,
    KGExtractionFullConfig,
)
from aurora_ext.rag.extraction.orchestrator import (
    BatchExtractionResult,
    ExtractionOrchestrator,
)
from aurora_ext.rag.extraction.types import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _make_result(
    chunk_id: str,
    n_entities: int = 2,
    n_relations: int = 1,
) -> ExtractionResult:
    entities = [
        ExtractedEntity(
            entity_name=f"Entity_{chunk_id}_{i}",
            entity_type="Person",
            entity_description=f"Description {i}",
            source_id=chunk_id,
        )
        for i in range(n_entities)
    ]
    relationships = [
        ExtractedRelationship(
            source_entity=f"Entity_{chunk_id}_0",
            target_entity=f"Entity_{chunk_id}_1",
            relationship_keywords="knows",
            relationship_description="Knows each other",
            source_id=chunk_id,
        )
        for _ in range(n_relations)
    ]
    return ExtractionResult(
        entities=entities,
        relationships=relationships,
        chunk_id=chunk_id,
    )


class FakeExtractor:
    """Test double that mimics EntityRelationExtractor.extract()."""

    def __init__(
        self,
        *,
        default_result: ExtractionResult | None = None,
        delay: float = 0.0,
        fail_chunk_ids: set[str] | None = None,
    ) -> None:
        self._default = default_result
        self._delay = delay
        self._fail_ids = fail_chunk_ids or set()
        self.call_count = 0

    async def extract(
        self,
        chunk_text: str,
        chunk_id: str,
        file_path: str = "",
        **config: Any,
    ) -> ExtractionResult:
        self.call_count += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if chunk_id in self._fail_ids:
            raise RuntimeError(f"Simulated failure for {chunk_id}")
        if self._default is not None:
            return ExtractionResult(
                entities=self._default.entities,
                relationships=self._default.relationships,
                chunk_id=chunk_id,
            )
        return _make_result(chunk_id)


# ── Tests ───────────────────────────────────────────────────────────


class TestExtractionOrchestrator:
    @pytest.mark.asyncio
    async def test_extract_single_basic(self) -> None:
        extractor = FakeExtractor()
        orch = ExtractionOrchestrator(extractor)

        result = await orch.extract_single(
            text="Alice knows Bob.",
            chunk_id="chunk-1",
        )
        assert result.chunk_id == "chunk-1"
        assert len(result.entities) == 2
        assert len(result.relationships) == 1
        assert extractor.call_count == 1

    @pytest.mark.asyncio
    async def test_extract_single_forwards_config(self) -> None:
        """Verify the orchestrator passes merged config kwargs to the extractor."""
        captured: dict[str, Any] = {}

        class CapturingExtractor:
            async def extract(self, chunk_text, chunk_id, file_path="", **config):
                captured.update(config)
                return ExtractionResult(chunk_id=chunk_id)

        orch = ExtractionOrchestrator(
            CapturingExtractor(),
            config=ExtractionConfig(max_total_records=50),
            addon=AddonParams(language="Chinese"),
            entity_type_config=EntityTypeConfig(
                custom_types=("Foo", "Bar"),
            ),
        )
        await orch.extract_single("text", "c1")

        assert captured["language"] == "Chinese"
        assert captured["max_total_records"] == 50
        assert "Foo" in captured["entity_types_guidance"]
        assert "Bar" in captured["entity_types_guidance"]

    @pytest.mark.asyncio
    async def test_extract_single_incremental_skip(self) -> None:
        extractor = FakeExtractor()
        processed: set[tuple[str, str]] = {("chunk-1", "hash-abc")}
        orch = ExtractionOrchestrator(
            extractor,
            config=ExtractionConfig(enable_incremental_extract=True),
            processed_chunks=processed,
        )

        result = await orch.extract_single(
            text="text",
            chunk_id="chunk-1",
            content_hash="hash-abc",
        )
        assert result.entities == []
        assert extractor.call_count == 0

    @pytest.mark.asyncio
    async def test_extract_single_incremental_processes_new(self) -> None:
        extractor = FakeExtractor()
        processed: set[tuple[str, str]] = {("chunk-1", "hash-abc")}
        orch = ExtractionOrchestrator(
            extractor,
            config=ExtractionConfig(enable_incremental_extract=True),
            processed_chunks=processed,
        )

        result = await orch.extract_single(
            text="text",
            chunk_id="chunk-2",
            content_hash="hash-def",
        )
        assert len(result.entities) == 2
        assert extractor.call_count == 1
        assert ("chunk-2", "hash-def") in orch._processed_chunks

    @pytest.mark.asyncio
    async def test_extract_batch_basic(self) -> None:
        extractor = FakeExtractor()
        orch = ExtractionOrchestrator(extractor)

        chunks = [
            {"text": f"Text {i}", "chunk_id": f"c-{i}"}
            for i in range(5)
        ]
        batch = await orch.extract_batch(chunks)

        assert isinstance(batch, BatchExtractionResult)
        assert batch.stats.total_chunks == 5
        assert batch.stats.successful_chunks == 5
        assert batch.stats.failed_chunks == 0
        assert batch.stats.total_entities == 10  # 2 per chunk
        assert batch.stats.total_relationships == 5
        assert extractor.call_count == 5

    @pytest.mark.asyncio
    async def test_extract_batch_concurrency_bounded(self) -> None:
        """Verify that max_parallel_extract limits concurrent extractions."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        class ConcurrencyTracker:
            async def extract(self, chunk_text, chunk_id, file_path="", **config):
                nonlocal max_concurrent, current_concurrent
                async with lock:
                    current_concurrent += 1
                    if current_concurrent > max_concurrent:
                        max_concurrent = current_concurrent
                await asyncio.sleep(0.05)
                async with lock:
                    current_concurrent -= 1
                return ExtractionResult(chunk_id=chunk_id)

        orch = ExtractionOrchestrator(
            ConcurrencyTracker(),
            config=ExtractionConfig(max_parallel_extract=2),
        )

        chunks = [{"text": "t", "chunk_id": f"c{i}"} for i in range(6)]
        await orch.extract_batch(chunks)

        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_extract_batch_error_isolation(self) -> None:
        """One failing chunk must not abort the rest."""
        extractor = FakeExtractor(fail_chunk_ids={"c-2"})
        orch = ExtractionOrchestrator(extractor)

        chunks = [
            {"text": f"Text {i}", "chunk_id": f"c-{i}"}
            for i in range(4)
        ]
        batch = await orch.extract_batch(chunks)

        assert batch.stats.total_chunks == 4
        assert batch.stats.failed_chunks == 1
        assert batch.stats.successful_chunks == 3
        assert len(batch.errors) == 1
        assert batch.errors[0]["chunk_id"] == "c-2"

    @pytest.mark.asyncio
    async def test_extract_batch_progress_callback(self) -> None:
        progress_log: list[tuple[int, int]] = []

        async def on_progress(completed: int, total: int) -> None:
            progress_log.append((completed, total))

        extractor = FakeExtractor()
        orch = ExtractionOrchestrator(extractor)

        chunks = [{"text": f"t{i}", "chunk_id": f"c{i}"} for i in range(3)]
        await orch.extract_batch(chunks, on_progress=on_progress)

        assert len(progress_log) == 3
        # Last entry should be (3, 3).
        assert progress_log[-1] == (3, 3)

    @pytest.mark.asyncio
    async def test_extract_batch_empty(self) -> None:
        extractor = FakeExtractor()
        orch = ExtractionOrchestrator(extractor)
        batch = await orch.extract_batch([])
        assert batch.stats.total_chunks == 0
        assert extractor.call_count == 0

    @pytest.mark.asyncio
    async def test_extract_batch_elapsed_time(self) -> None:
        extractor = FakeExtractor(delay=0.02)
        orch = ExtractionOrchestrator(
            extractor,
            config=ExtractionConfig(max_parallel_extract=5),
        )

        chunks = [{"text": f"t{i}", "chunk_id": f"c{i}"} for i in range(5)]
        batch = await orch.extract_batch(chunks)

        # With 5 chunks and parallelism=5, total time should be ~0.02s,
        # not ~0.10s sequential.
        assert batch.stats.elapsed_seconds < 0.15

    def test_from_full_config(self) -> None:
        extractor = FakeExtractor()
        full = KGExtractionFullConfig(
            extraction=ExtractionConfig(max_parallel_extract=8),
            addon=AddonParams(language="Japanese"),
        )
        orch = ExtractionOrchestrator.from_full_config(extractor, full)
        assert orch.config.max_parallel_extract == 8
        assert orch.addon.language == "Japanese"

    def test_processed_chunk_count(self) -> None:
        processed: set[tuple[str, str]] = {("a", "1"), ("b", "2")}
        orch = ExtractionOrchestrator(
            FakeExtractor(), processed_chunks=processed
        )
        assert orch.processed_chunk_count == 2
