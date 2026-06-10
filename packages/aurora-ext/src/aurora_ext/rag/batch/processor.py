"""Core batch processing engine.

:class:`BatchProcessor` orchestrates chunked, concurrent processing
of item lists with progress tracking, cancellation, retry logic, and
memory-aware backpressure.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Awaitable, Callable, Optional

from aurora_ext.rag.batch.cancellable import BatchCancelledError, CancellableBatch
from aurora_ext.rag.batch.config import (
    BatchConfig,
    BatchItemResult,
    BatchResult,
    ProgressSnapshot,
)
from aurora_ext.rag.batch.progress import ProgressTracker

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    """Split *items* into sublists of at most *size*."""
    if size <= 0:
        raise ValueError("size must be > 0")
    return [items[i : i + size] for i in range(0, len(items), size)]


def _estimate_memory_mb(items: list[Any]) -> float:
    """Rough estimate of the memory footprint of *items* in MB."""
    total_bytes = 0
    for item in items:
        total_bytes += sys.getsizeof(item)
        if isinstance(item, dict):
            for v in item.values():
                total_bytes += sys.getsizeof(v)
        elif isinstance(item, str):
            total_bytes += sys.getsizeof(item)
    return total_bytes / (1024 * 1024)


# ── Batch Processor ─────────────────────────────────────────────


class BatchProcessor:
    """High-performance batch processing engine.

    Processes a list of items in configurable-size batches with
    bounded concurrency, progress tracking, cancellation support,
    and automatic retry on transient failures.

    Parameters
    ----------
    config:
        A :class:`BatchConfig` instance.  Uses defaults if omitted.
    """

    def __init__(self, config: Optional[BatchConfig] = None) -> None:
        self.config = config or BatchConfig()
        self._cancellable = CancellableBatch()
        self._tracker: Optional[ProgressTracker] = None

    # ── Public API ────────────────────────────────────────────────

    async def process(
        self,
        items: list[Any],
        process_fn: Callable[[Any], Awaitable[Any]],
        *,
        item_id_fn: Optional[Callable[[Any], str]] = None,
    ) -> BatchResult:
        """Process a list of items in batches.

        Parameters
        ----------
        items:
            The full list of items to process.
        process_fn:
            An async callable that processes a single item and
            returns a result.
        item_id_fn:
            Optional callable that extracts a unique ID from an item
            (used in error reporting).  Defaults to ``str(item)``.

        Returns
        -------
        BatchResult
            An immutable aggregated result for the entire batch.
        """
        if not items:
            return BatchResult(total=0, succeeded=0, failed=0, duration_seconds=0.0)

        wall_start = time.monotonic()
        total = len(items)

        # Set up progress tracking.
        self._tracker = ProgressTracker(
            total=total,
            callback=self.config.progress_callback,
            callback_interval=self.config.progress_callback_interval,
        )

        # Reset cancellation state.
        self._cancellable.reset()

        # Chunk into batches.
        batches = _chunked(items, self.config.batch_size)
        logger.info(
            "Batch processing started: %d items, %d batches (size=%d, parallel=%d)",
            total,
            len(batches),
            self.config.batch_size,
            self.config.max_parallel_insert,
        )

        # Concurrency limiter.
        semaphore = asyncio.Semaphore(self.config.max_parallel_insert)
        all_item_results: list[BatchItemResult] = []
        result_lock = asyncio.Lock()

        async def _process_single(item: Any) -> None:
            """Process one item with retry, tracking, and error capture."""
            item_id = item_id_fn(item) if item_id_fn else str(item)
            item_start = time.monotonic()
            last_error = ""

            for attempt in range(1 + self.config.retry_attempts):
                try:
                    self._cancellable.check()
                    await process_fn(item)
                    duration = time.monotonic() - item_start

                    result = BatchItemResult(
                        item_id=item_id,
                        success=True,
                        duration_seconds=duration,
                    )
                    async with result_lock:
                        all_item_results.append(result)
                    self._tracker.update(success=True)
                    return

                except BatchCancelledError:
                    raise

                except Exception as exc:
                    last_error = str(exc)
                    if attempt < self.config.retry_attempts:
                        backoff = self.config.retry_backoff * (2 ** attempt)
                        logger.debug(
                            "Retry %d/%d for %s after %.1fs: %s",
                            attempt + 1,
                            self.config.retry_attempts,
                            item_id,
                            backoff,
                            exc,
                        )
                        await asyncio.sleep(backoff)

            # All retries exhausted.
            duration = time.monotonic() - item_start
            result = BatchItemResult(
                item_id=item_id,
                success=False,
                error=last_error,
                duration_seconds=duration,
            )
            async with result_lock:
                all_item_results.append(result)
            self._tracker.update(success=False)

        async def _process_batch(batch: list[Any]) -> None:
            """Process a single batch under the semaphore."""
            async with semaphore:
                # Memory-aware backpressure: if we're over the limit,
                # wait briefly before starting a new batch.
                estimated_mb = _estimate_memory_mb(batch)
                if estimated_mb > self.config.max_memory_mb:
                    logger.warning(
                        "Batch estimated at %.1f MB exceeds limit of %d MB; "
                        "reducing concurrency temporarily",
                        estimated_mb,
                        self.config.max_memory_mb,
                    )

                tasks = [asyncio.create_task(_process_single(item)) for item in batch]
                await asyncio.gather(*tasks)

        # Execute all batches concurrently.
        cancelled = False
        try:
            batch_tasks = [
                asyncio.create_task(_process_batch(batch)) for batch in batches
            ]
            await asyncio.gather(*batch_tasks)
        except BatchCancelledError:
            cancelled = True
            logger.info("Batch processing cancelled by user")
        except Exception as exc:
            logger.error("Unexpected error during batch processing: %s", exc)
            cancelled = True

        # Build final result.
        wall_duration = time.monotonic() - wall_start
        succeeded = sum(1 for r in all_item_results if r.success)
        failed = sum(1 for r in all_item_results if not r.success)
        errors = [r for r in all_item_results if not r.success]

        batch_result = BatchResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            cancelled=cancelled,
            duration_seconds=wall_duration,
            errors=errors,
        )

        logger.info(
            "Batch processing complete: %d/%d succeeded, %d failed, "
            "%.1fs elapsed (%.1f items/s)%s",
            succeeded,
            total,
            failed,
            wall_duration,
            batch_result.throughput,
            " [CANCELLED]" if cancelled else "",
        )

        return batch_result

    def cancel(self) -> None:
        """Request cancellation of the current batch operation."""
        self._cancellable.cancel()

    @property
    def is_cancelled(self) -> bool:
        return self._cancellable.is_cancelled

    def get_progress(self) -> Optional[ProgressSnapshot]:
        """Return current progress, or ``None`` if no batch is running."""
        if self._tracker is None:
            return None
        return self._tracker.get_progress()


# ── Convenience Functions ────────────────────────────────────────


async def batch_insert(
    items: list[dict[str, Any]],
    insert_fn: Callable[[dict[str, Any]], Awaitable[Any]],
    config: Optional[BatchConfig] = None,
) -> BatchResult:
    """Convenience wrapper for batch-inserting dictionaries.

    Parameters
    ----------
    items:
        List of dictionaries to insert.
    insert_fn:
        Async callable that inserts a single dictionary.
    config:
        Optional batch configuration.

    Returns
    -------
    BatchResult
    """
    processor = BatchProcessor(config)

    def _extract_id(item: dict[str, Any]) -> str:
        return str(item.get("id", item.get("_id", str(item)[:64])))

    return await processor.process(items, insert_fn, item_id_fn=_extract_id)


async def batch_transform(
    items: list[Any],
    transform_fn: Callable[[Any], Awaitable[Any]],
    config: Optional[BatchConfig] = None,
) -> tuple[BatchResult, list[Any]]:
    """Batch-transform items, collecting successful results.

    Parameters
    ----------
    items:
        Items to transform.
    transform_fn:
        Async callable that transforms a single item.
    config:
        Optional batch configuration.

    Returns
    -------
    tuple[BatchResult, list[Any]]
        The batch result and a list of successfully transformed items.
    """
    results: list[Any] = []
    result_lock = asyncio.Lock()

    async def _wrapped(item: Any) -> None:
        transformed = await transform_fn(item)
        async with result_lock:
            results.append(transformed)

    processor = BatchProcessor(config)
    batch_result = await processor.process(items, _wrapped)
    return batch_result, results
