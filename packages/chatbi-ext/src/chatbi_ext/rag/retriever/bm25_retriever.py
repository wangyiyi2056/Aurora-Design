from typing import List

from chatbi_ext.rag.knowledge.base import Document
from chatbi_ext.rag.retriever.base import BaseRetriever


class BM25Retriever(BaseRetriever):
    def __init__(self, documents: List[Document], top_k: int = 5):
        self.documents = documents
        self.top_k = top_k

    async def retrieve(self, query: str) -> List[Document]:
        # Simple substring ranking fallback
        ranked = sorted(
            self.documents,
            key=lambda d: d.content.lower().count(query.lower()),
            reverse=True,
        )
        return ranked[: self.top_k]
