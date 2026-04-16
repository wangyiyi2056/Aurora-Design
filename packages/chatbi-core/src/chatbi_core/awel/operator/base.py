from abc import ABC, abstractmethod
from typing import Any, List


class BaseOperator(ABC):
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.upstream: List["BaseOperator"] = []
        self.downstream: List["BaseOperator"] = []

    def __rshift__(self, other: "BaseOperator") -> "BaseOperator":
        self.downstream.append(other)
        other.upstream.append(self)
        return other

    @abstractmethod
    async def execute(self, task_ctx: Any) -> Any:
        ...


class MapOperator(BaseOperator):
    @abstractmethod
    async def map(self, input_value: Any) -> Any:
        ...

    async def execute(self, task_ctx: Any) -> Any:
        return await self.map(task_ctx)


class BranchOperator(BaseOperator):
    @abstractmethod
    async def branch(self, input_value: Any) -> str:
        """Return branch name based on input."""
        ...

    async def execute(self, task_ctx: Any) -> Any:
        return await self.branch(task_ctx)
