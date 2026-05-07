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
        ids = [f"doc-{i}" for i in range(len(texts))]
        self.collection.add(ids=ids, documents=texts, metadatas=metadatas)
        return ids

    def add_vectors(
        self,
        vectors: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> List[str]:
        ids = [f"vec-{i}" for i in range(len(texts))]
        self.collection.add(
            ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas
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
        for i in range(len(documents)):
            items.append(
                {
                    "content": documents[i],
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return items
