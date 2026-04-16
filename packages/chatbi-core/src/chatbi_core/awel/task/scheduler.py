import asyncio
from typing import Any, Callable, Coroutine


class TaskScheduler:
    """Simple async task scheduler."""

    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    def submit(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def gather(self) -> list[Any]:
        if not self._tasks:
            return []
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        return results
