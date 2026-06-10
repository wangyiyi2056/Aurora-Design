"""RAG storage layer — abstract base classes and default implementations.

Migrated from LightRAG storage architecture.  Four independent storage
abstractions allow mixing and matching backends:

* :class:`BaseKVStorage`         — key-value store (docs, chunks, cache)
* :class:`BaseVectorStorage`     — vector store (embeddings)
* :class:`BaseGraphStorage`      — graph store (entities, relationships)
* :class:`BaseDocStatusStorage`  — document processing state machine

Production backends (PostgreSQL, Neo4j, Milvus, Redis, MongoDB, Qdrant,
FAISS, OpenSearch, Memgraph, pgvector) are imported with ``try/except``
so that missing optional dependencies do not prevent the package from
loading.
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
from aurora_ext.rag.storage.workspace import (
    WorkspaceConfig,
    WorkspaceManager,
    default_workspace_manager,
    get_workspace_manager,
    validate_workspace_id,
)

# ── Storage registry ─────────────────────────────────────────────
_STORAGE_REGISTRY: dict[str, type] = {
    "JsonKVStorage": JsonKVStorage,
    "ChromaVectorStorage": ChromaVectorStorage,
    "NetworkXGraphStorage": NetworkXGraphStorage,
    "JsonDocStatusStorage": JsonDocStatusStorage,
}

# ── Optional production backends ─────────────────────────────────

# PostgreSQL
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

# Neo4j
try:
    from aurora_ext.rag.storage.neo4j_graph import Neo4jGraphStorage

    _STORAGE_REGISTRY["Neo4jGraphStorage"] = Neo4jGraphStorage
except ImportError:
    pass

# Milvus
try:
    from aurora_ext.rag.storage.milvus_vector import MilvusVectorStorage

    _STORAGE_REGISTRY["MilvusVectorStorage"] = MilvusVectorStorage
except ImportError:
    pass

# Redis
try:
    from aurora_ext.rag.storage.redis_kv import RedisKVStorage

    _STORAGE_REGISTRY["RedisKVStorage"] = RedisKVStorage
except ImportError:
    pass

# MongoDB
try:
    from aurora_ext.rag.storage.mongo_kv import MongoKVStorage

    _STORAGE_REGISTRY["MongoKVStorage"] = MongoKVStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.mongo_vector import MongoVectorDBStorage

    _STORAGE_REGISTRY["MongoVectorDBStorage"] = MongoVectorDBStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.mongo_doc_status import (
        MongoDocStatusStorage,
    )

    _STORAGE_REGISTRY["MongoDocStatusStorage"] = MongoDocStatusStorage
except ImportError:
    pass

# OpenSearch
try:
    from aurora_ext.rag.storage.opensearch_kv import OpenSearchKVStorage

    _STORAGE_REGISTRY["OpenSearchKVStorage"] = OpenSearchKVStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.opensearch_vector import (
        OpenSearchVectorDBStorage,
    )

    _STORAGE_REGISTRY["OpenSearchVectorDBStorage"] = OpenSearchVectorDBStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.opensearch_graph import (
        OpenSearchGraphStorage,
    )

    _STORAGE_REGISTRY["OpenSearchGraphStorage"] = OpenSearchGraphStorage
except ImportError:
    pass

try:
    from aurora_ext.rag.storage.opensearch_doc_status import (
        OpenSearchDocStatusStorage,
    )

    _STORAGE_REGISTRY["OpenSearchDocStatusStorage"] = OpenSearchDocStatusStorage
except ImportError:
    pass

# PostgreSQL + pgvector
try:
    from aurora_ext.rag.storage.pgvector import PGVectorStorage

    _STORAGE_REGISTRY["PGVectorStorage"] = PGVectorStorage
except ImportError:
    pass

# PostgreSQL graph (relational tables)
try:
    from aurora_ext.rag.storage.pg_graph import PGGraphStorage

    _STORAGE_REGISTRY["PGGraphStorage"] = PGGraphStorage
except ImportError:
    pass

# FAISS
try:
    from aurora_ext.rag.storage.faiss_vector import FaissVectorDBStorage

    _STORAGE_REGISTRY["FaissVectorDBStorage"] = FaissVectorDBStorage
except ImportError:
    pass

# Qdrant
try:
    from aurora_ext.rag.storage.qdrant_vector import QdrantVectorDBStorage

    _STORAGE_REGISTRY["QdrantVectorDBStorage"] = QdrantVectorDBStorage
except ImportError:
    pass

# Memgraph
try:
    from aurora_ext.rag.storage.memgraph_graph import MemgraphStorage

    _STORAGE_REGISTRY["MemgraphStorage"] = MemgraphStorage
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
    "FaissVectorDBStorage",
    "JsonDocStatusStorage",
    "JsonKVStorage",
    "MemgraphStorage",
    "MilvusVectorStorage",
    "MongoDocStatusStorage",
    "MongoKVStorage",
    "MongoVectorDBStorage",
    "Neo4jGraphStorage",
    "NetworkXGraphStorage",
    "OpenSearchDocStatusStorage",
    "OpenSearchGraphStorage",
    "OpenSearchKVStorage",
    "OpenSearchVectorDBStorage",
    "PGGraphStorage",
    "PGVectorStorage",
    "PostgresDocStatusStorage",
    "PostgresKVStorage",
    "QdrantVectorDBStorage",
    "RedisKVStorage",
    "StorageFactory",
    "StorageNameSpace",
    "WorkspaceConfig",
    "WorkspaceManager",
    "default_workspace_manager",
    "get_storage_class",
    "get_workspace_manager",
    "register_storage",
    "validate_workspace_id",
]
