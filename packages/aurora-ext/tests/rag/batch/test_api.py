"""Tests for the high-level async batch API."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from aurora_ext.rag.batch.api import AsyncBatchAPI
from aurora_ext.rag.batch.config import BatchConfig, BatchResult
from aurora_ext.rag.extraction.types import ExtractionResult


@pytest.fixture
def fast_config():
    return BatchConfig(
        max_parallel_insert=4,
        batch_size=10,
        retry_attempts=0,
        retry_backoff=0.0,
        progress_callback_interval=0.0,
    )


@pytest.fixture
def api(fast_config):
    return AsyncBatchAPI(config=fast_config)


# ── Single-item Operations ──────────────────────────────────────


class TestSingleItemOps:
    @pytest.mark.asyncio
    async def test_ainsert(self, api):
        insert_fn = AsyncMock(return_value="doc_123")

        result = await api.ainsert("Hello world", insert_fn)

        assert result == "doc_123"
        insert_fn.assert_awaited_once_with("Hello world")

    @pytest.mark.asyncio
    async def test_aextract(self, api):
        extraction = ExtractionResult(chunk_id="c1")
        extract_fn = AsyncMock(return_value=extraction)

        result = await api.aextract("Some text", extract_fn)

        assert isinstance(result, ExtractionResult)
        extract_fn.assert_awaited_once_with("Some text")

    @pytest.mark.asyncio
    async def test_aquery(self, api):
        query_fn = AsyncMock(return_value={"results": ["a", "b"]})

        result = await api.aquery("search term", query_fn)

        assert result == {"results": ["a", "b"]}
        query_fn.assert_awaited_once_with("search term")


# ── Batch Insert ─────────────────────────────────────────────────


class TestBatchInsert:
    @pytest.mark.asyncio
    async def test_abatch_insert_all_succeed(self, api):
        insert_fn = AsyncMock(side_effect=lambda t: f"id_{t[:10]}")

        texts = [f"Document {i}" for i in range(25)]
        result = await api.abatch_insert(texts, insert_fn)

        assert isinstance(result, BatchResult)
        assert result.total == 25
        assert result.succeeded == 25
        assert result.failed == 0
        assert insert_fn.await_count == 25

    @pytest.mark.asyncio
    async def test_abatch_insert_partial_failure(self, api):
        call_count = 0

        async def flaky_insert(text):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError("insert failed")
            return f"id_{call_count}"

        texts = [f"Doc {i}" for i in range(15)]
        result = await api.abatch_insert(texts, flaky_insert)

        assert result.total == 15
        assert result.failed == 5
        assert result.succeeded == 10

    @pytest.mark.asyncio
    async def test_abatch_insert_empty(self, api):
        insert_fn = AsyncMock()

        result = await api.abatch_insert([], insert_fn)

        assert result.total == 0
        insert_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_abatch_insert_custom_config(self, api):
        insert_fn = AsyncMock(return_value="ok")

        custom = BatchConfig(max_parallel_insert=1, batch_size=5, retry_attempts=0)
        texts = ["a", "b", "c"]
        result = await api.abatch_insert(texts, insert_fn, config=custom)

        assert result.total == 3
        assert result.succeeded == 3


# ── Batch Extract ────────────────────────────────────────────────


class TestBatchExtract:
    @pytest.mark.asyncio
    async def test_abatch_extract(self, api):
        async def mock_extract(text):
            return ExtractionResult(chunk_id=text[:10])

        texts = ["Text one", "Text two", "Text three"]
        batch_result, extractions = await api.abatch_extract(texts, mock_extract)

        assert batch_result.total == 3
        assert batch_result.succeeded == 3
        assert len(extractions) == 3
        assert all(isinstance(e, ExtractionResult) for e in extractions)

    @pytest.mark.asyncio
    async def test_abatch_extract_with_failures(self, api):
        async def flaky_extract(text):
            if "fail" in text:
                raise RuntimeError("extraction error")
            return ExtractionResult(chunk_id=text[:5])

        texts = ["good text", "fail text", "also good"]
        batch_result, extractions = await api.abatch_extract(texts, flaky_extract)

        assert batch_result.total == 3
        assert batch_result.succeeded == 2
        assert batch_result.failed == 1
        assert len(extractions) == 2


# ── Batch Query ──────────────────────────────────────────────────


class TestBatchQuery:
    @pytest.mark.asyncio
    async def test_abatch_query(self, api):
        async def mock_query(query):
            return {"query": query, "results": [1, 2, 3]}

        queries = ["q1", "q2", "q3", "q4"]
        batch_result, query_results = await api.abatch_query(queries, mock_query)

        assert batch_result.total == 4
        assert batch_result.succeeded == 4
        assert len(query_results) == 4


# ── Progress & Cancellation ─────────────────────────────────────


class TestProgressAndCancellation:
    @pytest.mark.asyncio
    async def test_get_progress_after_batch(self, api):
        insert_fn = AsyncMock(return_value="ok")

        await api.abatch_insert(["a", "b"], insert_fn)

        progress = api.get_progress()
        assert progress is not None
        assert progress.total == 2
        assert progress.completed == 2

    @pytest.mark.asyncio
    async def test_cancel_during_batch(self, fast_config):
        api = AsyncBatchAPI(config=fast_config)
        processed_count = 0

        async def slow_insert(text):
            nonlocal processed_count
            await asyncio.sleep(0.05)
            processed_count += 1
            return "ok"

        texts = [f"doc_{i}" for i in range(100)]
        task = asyncio.create_task(api.abatch_insert(texts, slow_insert))

        await asyncio.sleep(0.1)
        api.cancel_all()

        result = await task

        assert result.cancelled is True
        assert processed_count < 100

    def test_get_progress_no_batch(self, api):
        assert api.get_progress() is None

    def test_get_all_progress_empty(self, api):
        assert api.get_all_progress() == {}

    def test_cancel_unknown_op(self, api):
        assert api.cancel("nonexistent") is False
