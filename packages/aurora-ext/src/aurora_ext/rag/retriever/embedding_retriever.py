from typing import Any, Dict, List

from aurora_core.model.base import BaseEmbeddings
from aurora_ext.rag.knowledge.base import Document
from aurora_ext.rag.retrieval.citation_tracker import distance_to_score
from aurora_ext.rag.retriever.base import BaseRetriever
from aurora_ext.storage.base import VectorStoreBase


class EmbeddingRetriever(BaseRetriever):
    """Vector similarity retriever that preserves citation metadata.

    Each returned :class:`Document` includes the following metadata
    keys (when available from the vector store):

    * ``chunk_id``, ``file_path``, ``page_number``
    * ``start_pos``, ``end_pos``
    * ``score`` — similarity score in [0, 1]
    * ``distance`` — raw distance from the vector store
    """

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
        return [self._to_document(r) for r in results]

    async def retrieve_raw(self, query: str) -> List[Dict[str, Any]]:
        """Like :meth:`retrieve` but returns raw dicts for citation building."""
        vectors = await self.embeddings.aembed([query])
        results = self.vector_store.search(vectors[0], top_k=self.top_k)
        enriched: list[dict[str, Any]] = []
        for r in results:
            meta = r.get("metadata", {})
            score = distance_to_score(r.get("distance"))
            enriched.append({
                "content": r.get("content", ""),
                "chunk_id": r.get("chunk_id") or meta.get("chunk_id", r.get("id", "")),
                "file_path": r.get("file_path") or meta.get("file_path", meta.get("source", "")),
                "page_number": r.get("page_number") or meta.get("page_number"),
                "start_pos": r.get("start_pos") or meta.get("start_pos"),
                "end_pos": r.get("end_pos") or meta.get("end_pos"),
                "score": score,
                "distance": r.get("distance"),
            })
        return enriched

    @staticmethod
    def _to_document(result: Dict[str, Any]) -> Document:
        meta = dict(result.get("metadata", {}))
        meta.setdefault("chunk_id", result.get("chunk_id", result.get("id", "")))
        meta.setdefault("file_path", result.get("file_path", meta.get("source", "")))
        meta.setdefault("page_number", result.get("page_number"))
        meta.setdefault("start_pos", result.get("start_pos"))
        meta.setdefault("end_pos", result.get("end_pos"))
        meta["score"] = distance_to_score(result.get("distance"))
        meta["distance"] = result.get("distance")
        return Document(content=result.get("content", ""), metadata=meta)
