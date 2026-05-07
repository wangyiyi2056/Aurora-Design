from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


class BaseOperator:
    """Base AWEL operator with dependency wiring via ``>>``."""

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__
        self.downstream: list[BaseOperator] = []
        self.upstream: list[BaseOperator] = []

    def __rshift__(self, other: "BaseOperator") -> "BaseOperator":
        if other not in self.downstream:
            self.downstream.append(other)
        if self not in other.upstream:
            other.upstream.append(self)
        return other

    async def execute(self, input_value: Any) -> Any:
        raise NotImplementedError


class MapOperator(BaseOperator):
    """Single-step mapping operator."""

    async def map(self, input_value: Any) -> Any:
        return input_value

    async def execute(self, input_value: Any) -> Any:
        return await self.map(input_value)


class BranchOperator(BaseOperator):
    """Simple conditional branch operator reserved for workflow routing."""

    def __init__(
        self,
        name: str | None = None,
        condition: Callable[[Any], bool] | None = None,
    ):
        super().__init__(name=name)
        self.condition = condition or (lambda value: bool(value))

    async def execute(self, input_value: Any) -> bool:
        return bool(self.condition(input_value))


@dataclass
class DAG:
    nodes: dict[str, BaseOperator]


class DAGBuilder:
    def __init__(self):
        self._nodes: dict[str, BaseOperator] = {}

    def add_node(self, operator: BaseOperator) -> "DAGBuilder":
        if operator.name in self._nodes and self._nodes[operator.name] is not operator:
            raise ValueError(f"Duplicate operator name: {operator.name}")
        self._nodes[operator.name] = operator
        return self

    def build(self) -> DAG:
        for operator in list(self._nodes.values()):
            for linked in [*operator.upstream, *operator.downstream]:
                self._nodes.setdefault(linked.name, linked)
        self._assert_acyclic()
        return DAG(nodes=dict(self._nodes))

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(operator: BaseOperator) -> None:
            if operator.name in visited:
                return
            if operator.name in visiting:
                raise ValueError("DAG contains a cycle")
            visiting.add(operator.name)
            for child in operator.downstream:
                visit(child)
            visiting.remove(operator.name)
            visited.add(operator.name)

        for operator in self._nodes.values():
            visit(operator)


class DAGExecutor:
    def __init__(self, dag: DAG):
        self.dag = dag

    async def execute(self, initial_input: Any) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for operator in self._topological_order():
            if not operator.upstream:
                context = initial_input
            else:
                upstream_outputs = [outputs[parent.name] for parent in operator.upstream]
                context = upstream_outputs[0] if len(upstream_outputs) == 1 else upstream_outputs
            outputs[operator.name] = await operator.execute(context)
        return outputs

    def _topological_order(self) -> list[BaseOperator]:
        indegree = {name: 0 for name in self.dag.nodes}
        for operator in self.dag.nodes.values():
            for child in operator.downstream:
                if child.name in indegree:
                    indegree[child.name] += 1

        queue = [self.dag.nodes[name] for name, degree in indegree.items() if degree == 0]
        ordered: list[BaseOperator] = []
        while queue:
            operator = queue.pop(0)
            ordered.append(operator)
            for child in operator.downstream:
                if child.name not in indegree:
                    continue
                indegree[child.name] -= 1
                if indegree[child.name] == 0:
                    queue.append(child)

        if len(ordered) != len(self.dag.nodes):
            raise ValueError("DAG contains a cycle")
        return ordered


class TaskScheduler:
    async def run_all(self, coroutines: Iterable[Any]) -> list[Any]:
        return list(await asyncio.gather(*coroutines))


@dataclass
class OperatorMetadata:
    name: str
    operator_type: str
    description: str = ""


@dataclass
class FlowMetadata:
    name: str
    operators: list[OperatorMetadata] = field(default_factory=list)


__all__ = [
    "BaseOperator",
    "BranchOperator",
    "DAG",
    "DAGBuilder",
    "DAGExecutor",
    "FlowMetadata",
    "MapOperator",
    "OperatorMetadata",
    "TaskScheduler",
]
