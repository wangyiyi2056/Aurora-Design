from typing import Any, List

from aurora_core.model.base import BaseEmbeddings
from aurora_ext.rag.knowledge.base import Document
from aurora_ext.rag.operators.base import BaseOperator
from aurora_ext.rag.transformer.chunk import ChunkManager
from aurora_ext.storage.base import VectorStoreBase


class VectorStorageOperator(BaseOperator):
    def __init__(
        self,
        chunk_manager: ChunkManager,
        embeddings: BaseEmbeddings,
        vector_store: VectorStoreBase,
    ):
        self.chunk_manager = chunk_manager
        self.embeddings = embeddings
        self.vector_store = vector_store

    async def execute(self, documents: List[Document]) -> List[str]:
        chunks = self.chunk_manager.split(documents)
        texts = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        vectors = await self.embeddings.aembed(texts)
        return self.vector_store.add_vectors(vectors, texts, metadatas)
