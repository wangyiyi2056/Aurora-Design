from typing import List, Set

from chatbi_core.awel.dag.dag import DAG
from chatbi_core.awel.operator.base import BaseOperator


class DAGBuilder:
    def __init__(self):
        self._nodes: List[BaseOperator] = []

    def add_node(self, op: BaseOperator) -> "DAGBuilder":
        if op not in self._nodes:
            self._nodes.append(op)
        return self

    def build(self) -> DAG:
        # Auto-collect nodes from upstream/downstream links
        all_nodes: Set[BaseOperator] = set()
        for node in self._nodes:
            all_nodes.add(node)
            all_nodes.update(node.upstream)
            all_nodes.update(node.downstream)
        return DAG(nodes=list(all_nodes))
