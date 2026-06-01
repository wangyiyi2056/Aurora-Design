"""RAG storage layer — abstract base classes and default implementations.

Migrated from LightRAG storage architecture.  Four independent storage
abstractions allow mixing and matching backends:

* :class:`BaseKVStorage`         — key-value store (docs, chunks, cache)
* :class:`BaseVectorStorage`     — vector store (embeddings)
* :class:`BaseGraphStorage`      — graph store (entities, relationships)
* :class:`BaseDocStatusStorage`  — document processing state machine
"""

from aurora_ext.rag.storage.base import (
    BaseDocStatusStorage,
    BaseGraphStorage,
    BaseKVStorage,
    BaseVectorStorage,
    DocStatus,
    DocStatusInfo,
    StorageNameSpace,
)
from aurora_ext.rag.storage.chroma_vector import ChromaVectorStorage
from aurora_ext.rag.storage.json_doc_status import JsonDocStatusStorage
from aurora_ext.rag.storage.json_kv import JsonKVStorage
from aurora_ext.rag.storage.networkx_graph import NetworkXGraphStorage

# ── Storage registry ─────────────────────────────────────────────
_STORAGE_REGISTRY: dict[str, type] = {
    "JsonKVStorage": JsonKVStorage,
    "ChromaVectorStorage": ChromaVectorStorage,
    "NetworkXGraphStorage": NetworkXGraphStorage,
    "JsonDocStatusStorage": JsonDocStatusStorage,
}


def get_storage_class(name: str) -> type:
    """Look up a storage class by name.

    Raises ``KeyError`` when *name* is not registered.
    """
    if name not in _STORAGE_REGISTRY:
        available = ", ".join(sorted(_STORAGE_REGISTRY))
        raise KeyError(f"Unknown storage class '{name}'. Available: {available}")
    return _STORAGE_REGISTRY[name]


def register_storage(name: str, cls: type) -> None:
    """Register a custom storage backend."""
    _STORAGE_REGISTRY[name] = cls


__all__ = [
    "BaseDocStatusStorage",
    "BaseGraphStorage",
    "BaseKVStorage",
    "BaseVectorStorage",
    "ChromaVectorStorage",
    "DocStatus",
    "DocStatusInfo",
    "JsonDocStatusStorage",
    "JsonKVStorage",
    "NetworkXGraphStorage",
    "StorageNameSpace",
    "get_storage_class",
    "register_storage",
]
