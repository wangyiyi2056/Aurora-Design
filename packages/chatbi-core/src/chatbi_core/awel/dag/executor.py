from typing import Any, Dict, List

from chatbi_core.awel.dag.dag import DAG
from chatbi_core.awel.operator.base import BaseOperator


class DAGExecutor:
    def __init__(self, dag: DAG):
        self.dag = dag

    def _topological_sort(self) -> List[BaseOperator]:
        in_degree = {node: 0 for node in self.dag.nodes}
        for node in self.dag.nodes:
            for downstream in node.downstream:
                if downstream in in_degree:
                    in_degree[downstream] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for downstream in node.downstream:
                if downstream in in_degree:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        queue.append(downstream)
        return result

    async def execute(self, initial_input: Any = None) -> Dict[str, Any]:
        sorted_nodes = self._topological_sort()
        outputs: Dict[str, Any] = {}
        for node in sorted_nodes:
            # If node has upstream, collect their outputs as list
            if node.upstream:
                ctx = [outputs.get(u.name) for u in node.upstream]
                if len(ctx) == 1:
                    ctx = ctx[0]
            else:
                ctx = initial_input
            outputs[node.name] = await node.execute(ctx)
        return outputs
