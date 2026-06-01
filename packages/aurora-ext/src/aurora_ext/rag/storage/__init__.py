"""RAG storage layer — abstract base classes and default implementations.

Migrated from LightRAG storage architecture.  Four independent storage
abstractions allow mixing and matching backends:

* :class:`BaseKVStorage`         — key-value store (docs, chunks, cache)
* :class:`BaseVectorStorage`     — vector store (embeddings)
* :class:`BaseGraphStorage`      — graph store (entities, relationships)
* :class:`BaseDocStatusStorage`  — document processing state machine

Production backends (PostgreSQL, Neo4j, Milvus) are imported with
``try/except`` so that missing optional dependencies do not prevent the
package from loading.
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
from aurora_ext.rag.storage.factory import StorageFactory
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

# ── Optional production backends ─────────────────────────────────
try:
    from aurora_ext.rag.storage.postgres_kv import PostgresKVStorage

    _STORAGE_REGISTRY["PostgresKVStorage"] = PostgresKVStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.postgres_doc_status import (
        PostgresDocStatusStorage,
    )

    _STORAGE_REGISTRY["PostgresDocStatusStorage"] = PostgresDocStatusStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.neo4j_graph import Neo4jGraphStorage

    _STORAGE_REGISTRY["Neo4jGraphStorage"] = Neo4jGraphStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.milvus_vector import MilvusVectorStorage

    _STORAGE_REGISTRY["MilvusVectorStorage"] = MilvusVectorStorage
except ImportError:
    pass


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
    "MilvusVectorStorage",
    "Neo4jGraphStorage",
    "NetworkXGraphStorage",
    "PostgresDocStatusStorage",
    "PostgresKVStorage",
    "StorageFactory",
    "StorageNameSpace",
    "get_storage_class",
    "register_storage",
]
