"""Cancellation support for long-running batch operations.

Provides :class:`CancellableBatch` — a lightweight cooperative
cancellation mechanism built on :class:`asyncio.Event`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class BatchCancelledError(Exception):
    """Raised when a batch operation is cancelled."""


class CancellableBatch:
    """Wraps a batch loop with cooperative cancellation.

    Usage::

        batch = CancellableBatch()
        task = asyncio.create_task(batch.execute(items, process_fn))

        # Later…
        batch.cancel()
        # The next iteration raises BatchCancelledError.

    Parameters
    ----------
    on_cancel:
        Optional callback invoked when cancellation is requested.
    """

    def __init__(self, on_cancel: Callable[[], Any] | None = None) -> None:
        self._cancel_event = asyncio.Event()
        self._on_cancel = on_cancel

    # ── Public API ────────────────────────────────────────────────

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Request cancellation.

        Idempotent — calling multiple times has no additional effect.
        """
        if not self._cancel_event.is_set():
            logger.info("Batch cancellation requested")
            self._cancel_event.set()
            if self._on_cancel is not None:
                try:
                    self._on_cancel()
                except Exception:
                    logger.exception("Error in on_cancel callback")

    def reset(self) -> None:
        """Clear the cancellation flag so the instance can be reused."""
        self._cancel_event.clear()

    def check(self) -> None:
        """Raise :class:`BatchCancelledError` if cancelled.

        Call this at checkpoints inside a processing loop.
        """
        if self._cancel_event.is_set():
            raise BatchCancelledError("Batch operation was cancelled")

    async def execute(
        self,
        items: list[Any],
        process_fn: Callable[[Any], Awaitable[Any]],
    ) -> tuple[list[Any], list[Exception]]:
        """Process *items* one by one, checking cancellation between each.

        Parameters
        ----------
        items:
            The items to process.
        process_fn:
            An async callable that processes a single item.

        Returns
        -------
        tuple[list[Any], list[Exception]]
            A tuple of ``(results, errors)`` where *results* contains
            the return values of successful processing and *errors*
            contains exceptions from failed items.

        Raises
        ------
        BatchCancelledError
            If :meth:`cancel` was called before all items are processed.
        """
        results: list[Any] = []
        errors: list[Exception] = []

        for idx, item in enumerate(items):
            self.check()

            try:
                result = await process_fn(item)
                results.append(result)
            except BatchCancelledError:
                raise
            except Exception as exc:
                logger.warning("Item %d failed: %s", idx, exc)
                errors.append(exc)

        return results, errors
