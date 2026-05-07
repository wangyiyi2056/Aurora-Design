from typing import List

from aurora_core.model.base import BaseEmbeddings
from aurora_ext.rag.assembler.base import BaseAssembler
from aurora_ext.rag.knowledge.base import BaseKnowledge, Document
from aurora_ext.rag.retriever.base import BaseRetriever
from aurora_ext.rag.retriever.embedding_retriever import EmbeddingRetriever
from aurora_ext.rag.transformer.chunk import ChunkManager
from aurora_ext.storage.base import VectorStoreBase


class EmbeddingAssembler(BaseAssembler):
    def __init__(
        self,
        knowledge: BaseKnowledge,
        chunk_manager: ChunkManager,
        embeddings: BaseEmbeddings,
        vector_store: VectorStoreBase,
    ):
        self.knowledge = knowledge
        self.chunk_manager = chunk_manager
        self.embeddings = embeddings
        self.vector_store = vector_store
        self._chunks: List[Document] = []

    def persist(self) -> List[str]:
        docs = self.knowledge.load()
        self._chunks = self.chunk_manager.split(docs)
        texts = [c.content for c in self._chunks]
        metadatas = [c.metadata for c in self._chunks]
        return self.vector_store.add(texts, metadatas)

    def as_retriever(self, top_k: int = 5) -> BaseRetriever:
        return EmbeddingRetriever(
            vector_store=self.vector_store,
            embeddings=self.embeddings,
            top_k=top_k,
        )
