from typing import List

from chatbi_core.model.base import BaseEmbeddings
from chatbi_ext.rag.knowledge.base import Document
from chatbi_ext.rag.retriever.base import BaseRetriever
from chatbi_ext.storage.base import VectorStoreBase


class EmbeddingRetriever(BaseRetriever):
    def __init__(
        self,
        vector_store: VectorStoreBase,
        embeddings: BaseEmbeddings,
        top_k: int = 5,
    ):
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.top_k = top_k

    async def retrieve(self, query: str) -> List[Document]:
        vectors = await self.embeddings.aembed([query])
        results = self.vector_store.search(vectors[0], top_k=self.top_k)
        return [
            Document(content=r["content"], metadata=r.get("metadata", {}))
            for r in results
        ]
