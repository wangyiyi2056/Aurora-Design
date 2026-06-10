"""Thread-safe progress tracking for batch operations.

Provides :class:`ProgressTracker` — a monotonic counter that
produces immutable :class:`ProgressSnapshot` values on demand.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable, Optional

from aurora_ext.rag.batch.config import ProgressSnapshot


class ProgressTracker:
    """Tracks batch operation progress in a thread-safe manner.

    All mutating methods acquire an internal lock so that multiple
    async tasks or threads can report progress concurrently.

    Parameters
    ----------
    total:
        The total number of items to process.
    callback:
        Optional callable invoked with a :class:`ProgressSnapshot`
        whenever progress is updated.
    callback_interval:
        Minimum seconds between callback invocations (rate limiter).
    """

    def __init__(
        self,
        total: int,
        callback: Optional[Callable[[ProgressSnapshot], Any]] = None,
        callback_interval: float = 0.0,
    ) -> None:
        if total < 0:
            raise ValueError("total must be >= 0")

        self._total = total
        self._completed = 0
        self._failed = 0
        self._start_time = time.monotonic()
        self._lock = Lock()
        self._callback = callback
        self._callback_interval = callback_interval
        self._last_callback_time: float = 0.0

    # ── Mutation ────────────────────────────────────────────────────

    def update(self, *, success: bool = True, count: int = 1) -> ProgressSnapshot:
        """Record completion of one or more items.

        Parameters
        ----------
        success:
            ``True`` for successful items, ``False`` for failures.
        count:
            Number of items to add (default 1).

        Returns
        -------
        ProgressSnapshot
            An immutable snapshot of current progress.
        """
        with self._lock:
            if success:
                self._completed += count
            else:
                self._failed += count

            snapshot = self._snapshot_unlocked()
            self._maybe_callback(snapshot)
            return snapshot

    def reset(self, total: int) -> None:
        """Reset the tracker for a new batch.

        Parameters
        ----------
        total:
            New total item count.
        """
        with self._lock:
            self._total = total
            self._completed = 0
            self._failed = 0
            self._start_time = time.monotonic()
            self._last_callback_time = 0.0

    # ── Read ────────────────────────────────────────────────────────

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def completed(self) -> int:
        with self._lock:
            return self._completed

    @property
    def failed(self) -> int:
        with self._lock:
            return self._failed

    def get_progress(self) -> ProgressSnapshot:
        """Return an immutable snapshot of current progress."""
        with self._lock:
            return self._snapshot_unlocked()

    # ── Internals ──────────────────────────────────────────────────

    def _snapshot_unlocked(self) -> ProgressSnapshot:
        """Build a snapshot.  Caller must hold ``_lock``."""
        elapsed = time.monotonic() - self._start_time
        done = self._completed + self._failed
        progress_pct = (done / self._total * 100.0) if self._total > 0 else 100.0
        throughput = done / elapsed if elapsed > 0 else 0.0

        remaining_items = self._total - done
        if throughput > 0 and remaining_items > 0:
            estimated_remaining = remaining_items / throughput
        else:
            estimated_remaining = -1.0 if remaining_items > 0 else 0.0

        return ProgressSnapshot(
            total=self._total,
            completed=self._completed,
            failed=self._failed,
            progress_pct=progress_pct,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining,
            throughput=throughput,
        )

    def _maybe_callback(self, snapshot: ProgressSnapshot) -> None:
        """Invoke the callback if the rate limit allows."""
        if self._callback is None:
            return

        now = time.monotonic()
        if (now - self._last_callback_time) < self._callback_interval:
            return

        self._last_callback_time = now
        try:
            self._callback(snapshot)
        except Exception:
            # Callbacks must never break the tracker.
            pass
