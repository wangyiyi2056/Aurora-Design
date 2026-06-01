"""High-level async batch API.

:class:`AsyncBatchAPI` wraps lower-level batch primitives and provides
a unified async interface for insert, extract, and query operations
with progress tracking and cancellation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from aurora_ext.rag.batch.config import BatchConfig, BatchResult, ProgressSnapshot
from aurora_ext.rag.batch.processor import BatchProcessor
from aurora_ext.rag.extraction.types import ExtractionResult

logger = logging.getLogger(__name__)


# ── Result wrappers for typed operations ─────────────────────────


class InsertResult:
    """Result of an async insert operation."""

    def __init__(self, item_id: str, success: bool, error: str = "") -> None:
        self.item_id = item_id
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        status = "ok" if self.success else f"fail({self.error})"
        return f"InsertResult({self.item_id!r}, {status})"


# ── Async Batch API ──────────────────────────────────────────────


class AsyncBatchAPI:
    """Unified async interface for batch RAG operations.

    All methods have an ``a`` prefix and are async.  They accept
    callables for the actual storage/extraction backends so that
    the API layer is decoupled from specific implementations.

    Parameters
    ----------
    config:
        Batch configuration.  Defaults to :class:`BatchConfig` defaults.

    Example::

        api = AsyncBatchAPI(config=BatchConfig(max_parallel_insert=20))

        # Batch insert texts
        result = await api.abatch_insert(
            texts=["doc1", "doc2", "doc3"],
            insert_fn=my_storage.ainsert,
        )

        # Check progress
        snapshot = api.get_progress()
    """

    def __init__(self, config: Optional[BatchConfig] = None) -> None:
        self.config = config or BatchConfig()
        self._processor: Optional[BatchProcessor] = None
        self._active_operations: dict[str, BatchProcessor] = {}

    # ── Single-item async operations ──────────────────────────────

    async def ainsert(
        self,
        text: str,
        insert_fn: Callable[[str], Awaitable[str]],
    ) -> str:
        """Insert a single text asynchronously.

        Parameters
        ----------
        text:
            The text content to insert.
        insert_fn:
            Async callable that performs the insert and returns an ID.

        Returns
        -------
        str
            The ID of the inserted item.
        """
        return await insert_fn(text)

    async def aextract(
        self,
        text: str,
        extract_fn: Callable[[str], Awaitable[ExtractionResult]],
    ) -> ExtractionResult:
        """Extract entities and relationships from text asynchronously.

        Parameters
        ----------
        text:
            The text to extract from.
        extract_fn:
            Async callable that performs extraction.

        Returns
        -------
        ExtractionResult
        """
        return await extract_fn(text)

    async def aquery(
        self,
        query: str,
        query_fn: Callable[[str], Awaitable[Any]],
    ) -> Any:
        """Execute a query asynchronously.

        Parameters
        ----------
        query:
            The query string.
        query_fn:
            Async callable that performs the query.

        Returns
        -------
        Any
            The query result (type depends on the backend).
        """
        return await query_fn(query)

    # ── Batch operations ──────────────────────────────────────────

    async def abatch_insert(
        self,
        texts: list[str],
        insert_fn: Callable[[str], Awaitable[str]],
        *,
        config: Optional[BatchConfig] = None,
    ) -> BatchResult:
        """Batch-insert multiple texts asynchronously.

        Parameters
        ----------
        texts:
            List of text strings to insert.
        insert_fn:
            Async callable that inserts a single text.
        config:
            Optional per-call config override.

        Returns
        -------
        BatchResult
        """
        processor = BatchProcessor(config or self.config)
        self._processor = processor
        op_id = f"insert_{id(texts)}"
        self._active_operations[op_id] = processor

        try:
            result = await processor.process(
                texts,
                insert_fn,
                item_id_fn=lambda t: t[:64] if len(t) > 64 else t,
            )
        finally:
            self._active_operations.pop(op_id, None)

        return result

    async def abatch_extract(
        self,
        texts: list[str],
        extract_fn: Callable[[str], Awaitable[ExtractionResult]],
        *,
        config: Optional[BatchConfig] = None,
    ) -> tuple[BatchResult, list[ExtractionResult]]:
        """Batch-extract entities from multiple texts.

        Parameters
        ----------
        texts:
            List of text strings to extract from.
        extract_fn:
            Async callable that extracts from a single text.
        config:
            Optional per-call config override.

        Returns
        -------
        tuple[BatchResult, list[ExtractionResult]]
        """
        extraction_results: list[ExtractionResult] = []
        lock = asyncio.Lock()

        async def _wrapped(text: str) -> None:
            result = await extract_fn(text)
            async with lock:
                extraction_results.append(result)

        processor = BatchProcessor(config or self.config)
        self._processor = processor
        op_id = f"extract_{id(texts)}"
        self._active_operations[op_id] = processor

        try:
            batch_result = await processor.process(
                texts,
                _wrapped,
                item_id_fn=lambda t: t[:64] if len(t) > 64 else t,
            )
        finally:
            self._active_operations.pop(op_id, None)

        return batch_result, extraction_results

    async def abatch_query(
        self,
        queries: list[str],
        query_fn: Callable[[str], Awaitable[Any]],
        *,
        config: Optional[BatchConfig] = None,
    ) -> tuple[BatchResult, list[Any]]:
        """Batch-execute multiple queries.

        Parameters
        ----------
        queries:
            List of query strings.
        query_fn:
            Async callable that executes a single query.
        config:
            Optional per-call config override.

        Returns
        -------
        tuple[BatchResult, list[Any]]
        """
        query_results: list[Any] = []
        lock = asyncio.Lock()

        async def _wrapped(query: str) -> None:
            result = await query_fn(query)
            async with lock:
                query_results.append(result)

        processor = BatchProcessor(config or self.config)
        self._processor = processor
        op_id = f"query_{id(queries)}"
        self._active_operations[op_id] = processor

        try:
            batch_result = await processor.process(
                queries,
                _wrapped,
                item_id_fn=lambda q: q[:64] if len(q) > 64 else q,
            )
        finally:
            self._active_operations.pop(op_id, None)

        return batch_result, query_results

    # ── Progress & Cancellation ───────────────────────────────────

    def get_progress(self) -> Optional[ProgressSnapshot]:
        """Return progress of the most recent batch operation."""
        if self._processor is None:
            return None
        return self._processor.get_progress()

    def get_all_progress(self) -> dict[str, ProgressSnapshot]:
        """Return progress of all active batch operations."""
        result: dict[str, ProgressSnapshot] = {}
        for op_id, proc in self._active_operations.items():
            progress = proc.get_progress()
            if progress is not None:
                result[op_id] = progress
        return result

    def cancel_all(self) -> None:
        """Cancel all active batch operations."""
        if self._processor is not None:
            self._processor.cancel()
        for proc in self._active_operations.values():
            proc.cancel()

    def cancel(self, op_id: str) -> bool:
        """Cancel a specific batch operation.

        Returns ``True`` if the operation was found and cancelled.
        """
        proc = self._active_operations.get(op_id)
        if proc is not None:
            proc.cancel()
            return True
        return False
