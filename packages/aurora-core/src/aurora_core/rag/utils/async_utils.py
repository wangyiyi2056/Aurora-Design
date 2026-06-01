"""Async concurrency limiter with priority queue.

Migrated from LightRAG ``utils.priority_limit_async_func_call``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class _PrioritySemaphore:
    """Semaphore wrapper that processes tasks in FIFO order.

    Ensures fair scheduling when many coroutines compete for limited
    concurrency slots.
    """

    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: asyncio.Queue[asyncio.Event] = asyncio.Queue()

    async def acquire(self) -> None:
        gate = asyncio.Event()
        await self._queue.put(gate)
        await gate.wait()
        await self._semaphore.acquire()

    def release(self) -> None:
        self._semaphore.release()
        try:
            self._queue.get_nowait().set()
        except asyncio.QueueEmpty:
            pass


def priority_limit_async_func_call(
    max_concurrent: int,
    timeout: float = 180.0,
) -> Callable[..., Awaitable[Any]]:
    """Create a concurrency-limited async wrapper.

    Parameters
    ----------
    max_concurrent:
        Maximum number of simultaneous invocations.
    timeout:
        Per-call timeout in seconds.  ``0`` means no timeout.

    Returns
    -------
    Callable
        A decorator / wrapper that limits concurrency for the wrapped
        async function.

    Usage::

        limited = priority_limit_async_func_call(max_concurrent=4)
        result = await limited(some_async_fn, arg1, arg2)
    """
    sem = _PrioritySemaphore(max_concurrent)

    async def wrapper(func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        await sem.acquire()
        try:
            if timeout > 0:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            return await func(*args, **kwargs)
        except asyncio.TimeoutError:
            logger.warning("Async call timed out after %.1fs", timeout)
            raise
        finally:
            sem.release()

    return wrapper


class AsyncLimiter:
    """Stateful async concurrency limiter.

    Useful when the same limit applies across many call sites and you
    want to reuse a single limiter instance.

    Usage::

        limiter = AsyncLimiter(max_concurrent=4, timeout=60.0)
        result = await limiter.run(some_async_fn, arg1, arg2)
    """

    def __init__(self, max_concurrent: int, timeout: float = 180.0) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._timeout = timeout

    async def run(self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with concurrency limiting."""
        async with self._semaphore:
            if self._timeout > 0:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=self._timeout)
            return await func(*args, **kwargs)

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent
