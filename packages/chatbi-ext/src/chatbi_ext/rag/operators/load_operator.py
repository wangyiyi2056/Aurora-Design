from typing import Any, List

from chatbi_ext.rag.knowledge.base import BaseKnowledge, Document
from chatbi_ext.rag.operators.base import BaseOperator


class KnowledgeLoadOperator(BaseOperator):
    def __init__(self, knowledge: BaseKnowledge):
        self.knowledge = knowledge

    async def execute(self, input_value: Any = None) -> List[Document]:
        return self.knowledge.load()
