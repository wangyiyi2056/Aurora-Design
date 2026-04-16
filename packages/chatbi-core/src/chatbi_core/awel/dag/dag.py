from typing import List

from chatbi_core.awel.operator.base import BaseOperator


class DAG:
    def __init__(self, nodes: List[BaseOperator]):
        self.nodes = nodes
