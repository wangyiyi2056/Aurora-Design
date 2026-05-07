from abc import ABC, abstractmethod
from typing import Any, Dict, List


class VectorStoreBase(ABC):
    @abstractmethod
    def add(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        """Add texts with auto-generated embeddings."""

    @abstractmethod
    def add_vectors(
        self,
        vectors: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> List[str]:
        """Add pre-computed vectors."""

    @abstractmethod
    def search(self, vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search by vector and return results with content and metadata."""
