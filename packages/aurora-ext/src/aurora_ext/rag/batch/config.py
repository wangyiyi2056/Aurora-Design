"""Batch processing configuration and result types.

Provides immutable dataclasses for configuring batch operations
and reporting their results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Defaults ────────────────────────────────────────────────────

_DEFAULT_MAX_PARALLEL = 10
_DEFAULT_BATCH_SIZE = 100
_DEFAULT_MAX_MEMORY_MB = 2048
_DEFAULT_PROGRESS_INTERVAL_SEC = 5.0


# ── Configuration ───────────────────────────────────────────────


@dataclass(frozen=True)
class BatchConfig:
    """Immutable configuration for batch operations.

    Attributes
    ----------
    max_parallel_insert:
        Maximum number of concurrent insert tasks.
    batch_size:
        Number of items per batch chunk.
    enable_async:
        Whether to use async processing (``True``) or synchronous
        fallback (``False``).
    max_memory_mb:
        Soft memory cap in megabytes.  The processor will reduce
        concurrency when estimated memory usage exceeds this value.
    progress_callback_interval:
        Minimum seconds between progress callback invocations.
    progress_callback:
        Optional callable invoked with a :class:`ProgressSnapshot`
        on each progress tick.
    retry_attempts:
        Number of retry attempts for transient failures.
    retry_backoff:
        Base backoff multiplier for exponential retry delay.
    """

    max_parallel_insert: int = _DEFAULT_MAX_PARALLEL
    batch_size: int = _DEFAULT_BATCH_SIZE
    enable_async: bool = True
    max_memory_mb: int = _DEFAULT_MAX_MEMORY_MB
    progress_callback_interval: float = _DEFAULT_PROGRESS_INTERVAL_SEC
    progress_callback: Optional[Callable[..., Any]] = field(
        default=None, repr=False, compare=False
    )
    retry_attempts: int = 3
    retry_backoff: float = 1.0

    def __post_init__(self) -> None:
        if self.max_parallel_insert < 1:
            raise ValueError("max_parallel_insert must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_memory_mb < 64:
            raise ValueError("max_memory_mb must be >= 64")
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts must be >= 0")

    @staticmethod
    def from_toml(data: dict[str, Any]) -> BatchConfig:
        """Build a :class:`BatchConfig` from a TOML-style dict.

        Expected structure::

            [batch]
            max_parallel_insert = 10
            batch_size = 100
            enable_async = true
            max_memory_mb = 2048
            progress_callback_interval = 5
            retry_attempts = 3
            retry_backoff = 1.0
        """
        section = data.get("batch", data)
        known_fields = {f.name for f in BatchConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in section.items() if k in known_fields and k != "progress_callback"}
        return BatchConfig(**filtered)


# ── Result Types ────────────────────────────────────────────────


@dataclass(frozen=True)
class BatchItemResult:
    """Result for a single processed item.

    Attributes
    ----------
    item_id:
        Unique identifier of the item.
    success:
        Whether the item was processed successfully.
    error:
        Error message if the item failed, empty string otherwise.
    duration_seconds:
        Time spent processing this item.
    """

    item_id: str
    success: bool
    error: str = ""
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class BatchResult:
    """Aggregated result for an entire batch operation.

    Attributes
    ----------
    total:
        Total number of items submitted.
    succeeded:
        Number of items processed successfully.
    failed:
        Number of items that failed.
    cancelled:
        Whether the batch was cancelled before completion.
    duration_seconds:
        Wall-clock time for the entire batch.
    errors:
        List of :class:`BatchItemResult` entries for failed items.
    throughput:
        Items processed per second.
    """

    total: int
    succeeded: int
    failed: int
    cancelled: bool = False
    duration_seconds: float = 0.0
    errors: list[BatchItemResult] = field(default_factory=list)

    @property
    def throughput(self) -> float:
        """Items per second (total items / wall-clock seconds)."""
        if self.duration_seconds <= 0:
            return 0.0
        return self.total / self.duration_seconds

    @property
    def success_rate(self) -> float:
        """Fraction of items that succeeded (0.0 – 1.0)."""
        if self.total <= 0:
            return 0.0
        return self.succeeded / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "duration_seconds": round(self.duration_seconds, 3),
            "throughput": round(self.throughput, 1),
            "success_rate": round(self.success_rate, 4),
            "errors": [
                {
                    "item_id": e.item_id,
                    "error": e.error,
                    "duration_seconds": round(e.duration_seconds, 3),
                }
                for e in self.errors
            ],
        }


# ── Progress Snapshot ───────────────────────────────────────────


@dataclass(frozen=True)
class ProgressSnapshot:
    """Point-in-time progress information.

    Attributes
    ----------
    total:
        Total items to process.
    completed:
        Items successfully processed so far.
    failed:
        Items that have failed so far.
    progress_pct:
        Completion percentage (0.0 – 100.0).
    elapsed_seconds:
        Wall-clock time since the batch started.
    estimated_remaining_seconds:
        Estimated time until completion, or ``-1`` if unknown.
    throughput:
        Items processed per second so far.
    """

    total: int
    completed: int
    failed: int
    progress_pct: float
    elapsed_seconds: float
    estimated_remaining_seconds: float
    throughput: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "progress_pct": round(self.progress_pct, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 2),
            "throughput": round(self.throughput, 1),
        }
