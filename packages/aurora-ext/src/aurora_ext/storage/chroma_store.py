from typing import Any, Dict, List

import chromadb

from aurora_ext.storage.base import VectorStoreBase


class ChromaVectorStore(VectorStoreBase):
    def __init__(self, collection_name: str = "default", persist_directory: str | None = None):
        self.client = chromadb.Client()
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        ids = self._build_ids(metadatas, prefix="doc", count=len(texts))
        # ChromaDB metadata values must be str/int/float/bool
        safe_meta = [self._sanitize_metadata(m) for m in metadatas]
        self.collection.add(ids=ids, documents=texts, metadatas=safe_meta)
        return ids

    def add_vectors(
        self,
        vectors: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> List[str]:
        ids = self._build_ids(metadatas, prefix="vec", count=len(texts))
        safe_meta = [self._sanitize_metadata(m) for m in metadatas]
        self.collection.add(
            ids=ids, embeddings=vectors, documents=texts, metadatas=safe_meta
        )
        return ids

    def search(self, vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_embeddings=[vector], n_results=top_k
        )
        items = []
        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []
        ids = results.get("ids", [[]])[0] or []
        for i in range(len(documents)):
            meta = metadatas[i] if i < len(metadatas) else {}
            chunk_id = ids[i] if i < len(ids) else ""
            items.append(
                {
                    "content": documents[i],
                    "metadata": meta,
                    "id": chunk_id,
                    "chunk_id": meta.get("chunk_id", chunk_id),
                    "file_path": meta.get("file_path", meta.get("source", "")),
                    "page_number": meta.get("page_number"),
                    "start_pos": meta.get("start_pos"),
                    "end_pos": meta.get("end_pos"),
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return items

    @staticmethod
    def _build_ids(
        metadatas: List[Dict[str, Any]], prefix: str, count: int
    ) -> List[str]:
        """Use ``chunk_id`` from metadata when available, else generate."""
        ids: list[str] = []
        for i, meta in enumerate(metadatas):
            cid = meta.get("chunk_id") if meta else None
            if cid:
                ids.append(str(cid))
            else:
                ids.append(f"{prefix}-{i}")
        return ids

    @staticmethod
    def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """ChromaDB only accepts str/int/float/bool metadata values."""
        safe: dict[str, Any] = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                safe[k] = v
            elif isinstance(v, (list, tuple)):
                # Store as JSON string so it survives round-trips
                import json
                safe[k] = json.dumps(v, ensure_ascii=False)
            elif v is not None:
                safe[k] = str(v)
        return safe
