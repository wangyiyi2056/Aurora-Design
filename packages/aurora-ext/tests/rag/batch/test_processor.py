"""Tests for the batch processing engine."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from aurora_ext.rag.batch.config import BatchConfig, BatchResult
from aurora_ext.rag.batch.processor import (
    BatchProcessor,
    _chunked,
    _estimate_memory_mb,
    batch_insert,
    batch_transform,
)


# ── Helper Fixtures ──────────────────────────────────────────────


@pytest.fixture
def fast_config():
    """Config tuned for fast tests."""
    return BatchConfig(
        max_parallel_insert=4,
        batch_size=10,
        retry_attempts=0,
        retry_backoff=0.0,
        progress_callback_interval=0.0,
    )


@pytest.fixture
def sample_items():
    return [{"id": f"item_{i}", "text": f"Sample text {i}"} for i in range(50)]


# ── Chunking Helper ──────────────────────────────────────────────


class TestChunked:
    def test_exact_split(self):
        items = list(range(10))
        chunks = _chunked(items, 5)

        assert len(chunks) == 2
        assert chunks[0] == [0, 1, 2, 3, 4]
        assert chunks[1] == [5, 6, 7, 8, 9]

    def test_remainder(self):
        items = list(range(7))
        chunks = _chunked(items, 3)

        assert len(chunks) == 3
        assert chunks[-1] == [6]

    def test_single_chunk(self):
        items = [1, 2, 3]
        chunks = _chunked(items, 100)

        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_empty(self):
        assert _chunked([], 5) == []

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            _chunked([1, 2], 0)


# ── Memory Estimation ────────────────────────────────────────────


class TestEstimateMemory:
    def test_returns_positive(self):
        items = [{"key": "value"}, {"key": "another"}]
        mb = _estimate_memory_mb(items)
        assert mb > 0

    def test_empty_list(self):
        assert _estimate_memory_mb([]) == 0.0

    def test_strings(self):
        items = ["a" * 1000, "b" * 1000]
        mb = _estimate_memory_mb(items)
        assert mb > 0


# ── BatchProcessor ───────────────────────────────────────────────


class TestBatchProcessor:
    """Test the core batch processing engine."""

    @pytest.mark.asyncio
    async def test_process_empty_list(self, fast_config):
        processor = BatchProcessor(fast_config)

        async def noop(item):
            pass

        result = await processor.process([], noop)

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_process_all_succeed(self, fast_config, sample_items):
        processor = BatchProcessor(fast_config)

        async def process(item):
            return item["id"]

        result = await processor.process(
            sample_items, process, item_id_fn=lambda x: x["id"]
        )

        assert result.total == 50
        assert result.succeeded == 50
        assert result.failed == 0
        assert result.cancelled is False
        assert result.duration_seconds > 0
        assert result.throughput > 0
        assert result.success_rate == pytest.approx(1.0)
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_process_all_fail(self, fast_config, sample_items):
        processor = BatchProcessor(fast_config)

        async def failing_process(item):
            raise RuntimeError("intentional failure")

        result = await processor.process(
            sample_items, failing_process, item_id_fn=lambda x: x["id"]
        )

        assert result.total == 50
        assert result.succeeded == 0
        assert result.failed == 50
        assert len(result.errors) == 50

    @pytest.mark.asyncio
    async def test_process_partial_failure(self, fast_config, sample_items):
        processor = BatchProcessor(fast_config)

        async def selective_process(item):
            idx = int(item["id"].split("_")[1])
            if idx % 2 == 0:
                raise ValueError("even items fail")
            return item

        result = await processor.process(
            sample_items, selective_process, item_id_fn=lambda x: x["id"]
        )

        assert result.total == 50
        assert result.succeeded == 25
        assert result.failed == 25

    @pytest.mark.asyncio
    async def test_process_respects_concurrency(self):
        """Verify semaphore limits concurrent tasks."""
        config = BatchConfig(
            max_parallel_insert=2,
            batch_size=1,
            retry_attempts=0,
        )
        processor = BatchProcessor(config)

        active_count = 0
        max_active = 0
        lock = asyncio.Lock()

        async def tracked_process(item):
            nonlocal active_count, max_active
            async with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            await asyncio.sleep(0.01)
            async with lock:
                active_count -= 1

        items = list(range(20))
        await processor.process(items, tracked_process)

        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_process_with_retry(self, sample_items):
        config = BatchConfig(
            max_parallel_insert=4,
            batch_size=50,
            retry_attempts=2,
            retry_backoff=0.01,
        )
        processor = BatchProcessor(config)

        attempt_counts: dict[str, int] = {}

        async def flaky_process(item):
            item_id = item["id"]
            attempt_counts[item_id] = attempt_counts.get(item_id, 0) + 1
            if attempt_counts[item_id] < 3:
                raise RuntimeError("transient error")
            return item

        result = await processor.process(
            sample_items, flaky_process, item_id_fn=lambda x: x["id"]
        )

        assert result.total == 50
        assert result.succeeded == 50

    @pytest.mark.asyncio
    async def test_process_retry_exhausted(self):
        config = BatchConfig(
            max_parallel_insert=2,
            batch_size=10,
            retry_attempts=2,
            retry_backoff=0.01,
        )
        processor = BatchProcessor(config)

        async def always_fails(item):
            raise RuntimeError("permanent error")

        result = await processor.process(
            [{"id": "x"}], always_fails, item_id_fn=lambda x: x["id"]
        )

        assert result.total == 1
        assert result.failed == 1
        assert result.errors[0].error == "permanent error"

    @pytest.mark.asyncio
    async def test_cancellation(self, fast_config):
        processor = BatchProcessor(fast_config)
        processed = []

        async def slow_process(item):
            await asyncio.sleep(0.05)
            processed.append(item)
            return item

        items = list(range(100))

        # Start processing
        task = asyncio.create_task(
            processor.process(items, slow_process)
        )

        # Cancel after a short delay
        await asyncio.sleep(0.1)
        processor.cancel()

        result = await task

        assert result.cancelled is True
        assert len(processed) < 100

    @pytest.mark.asyncio
    async def test_progress_tracking(self, fast_config, sample_items):
        progress_snapshots = []

        def on_progress(snapshot):
            progress_snapshots.append(snapshot)

        config = BatchConfig(
            max_parallel_insert=4,
            batch_size=10,
            retry_attempts=0,
            progress_callback=on_progress,
            progress_callback_interval=0.0,
        )
        processor = BatchProcessor(config)

        async def process(item):
            return item

        await processor.process(sample_items, process)

        assert len(progress_snapshots) > 0
        final = progress_snapshots[-1]
        assert final.completed + final.failed == 50

    @pytest.mark.asyncio
    async def test_get_progress_during_batch(self, fast_config):
        processor = BatchProcessor(fast_config)
        progress_during = []

        async def tracked_process(item):
            await asyncio.sleep(0.01)
            p = processor.get_progress()
            if p is not None:
                progress_during.append(p)
            return item

        items = list(range(20))
        await processor.process(items, tracked_process)

        assert len(progress_during) > 0

    def test_get_progress_before_batch(self, fast_config):
        processor = BatchProcessor(fast_config)
        assert processor.get_progress() is None

    @pytest.mark.asyncio
    async def test_default_config(self):
        processor = BatchProcessor()
        assert processor.config.max_parallel_insert == 10

    @pytest.mark.asyncio
    async def test_throughput_calculation(self, fast_config):
        processor = BatchProcessor(fast_config)

        async def quick_process(item):
            return item

        items = list(range(100))
        start = time.monotonic()
        result = await processor.process(items, quick_process)
        elapsed = time.monotonic() - start

        assert result.throughput > 0
        assert result.duration_seconds > 0
        assert result.duration_seconds <= elapsed + 0.5  # some slack


# ── Convenience Functions ────────────────────────────────────────


class TestBatchInsert:
    @pytest.mark.asyncio
    async def test_basic_insert(self, fast_config):
        inserted = []

        async def mock_insert(item):
            inserted.append(item)
            return item.get("id", "unknown")

        items = [{"id": f"doc_{i}", "text": f"Text {i}"} for i in range(20)]
        result = await batch_insert(items, mock_insert, config=fast_config)

        assert result.total == 20
        assert result.succeeded == 20
        assert len(inserted) == 20


class TestBatchTransform:
    @pytest.mark.asyncio
    async def test_basic_transform(self, fast_config):
        async def double(item):
            return item * 2

        result, transformed = await batch_transform(
            [1, 2, 3, 4, 5], double, config=fast_config
        )

        assert result.total == 5
        assert result.succeeded == 5
        assert sorted(transformed) == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_transform_partial_failure(self, fast_config):
        async def maybe_fail(item):
            if item == 3:
                raise ValueError("nope")
            return item * 10

        result, transformed = await batch_transform(
            [1, 2, 3, 4, 5], maybe_fail, config=fast_config
        )

        assert result.total == 5
        assert result.succeeded == 4
        assert result.failed == 1
        assert sorted(transformed) == [10, 20, 40, 50]
