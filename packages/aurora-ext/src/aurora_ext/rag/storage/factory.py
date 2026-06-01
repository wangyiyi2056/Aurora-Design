"""Storage factory for creating storage backends by name.

Provides a registry-based factory pattern that auto-registers all
built-in storage backends.  Optional dependencies (PostgreSQL, Neo4j,
Milvus) are imported inside ``try/except`` blocks so that missing
packages do not crash the application.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from storage_type to {backend_name: class}
_STORAGE_TYPE_MAP: dict[str, dict[str, type]] = {
    "kv": {},
    "vector": {},
    "graph": {},
    "doc_status": {},
}


def _register_builtins() -> None:
    """Auto-register all built-in storage backends."""
    # ── KV backends ──────────────────────────────────────────
    try:
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        _STORAGE_TYPE_MAP["kv"]["json"] = JsonKVStorage
    except ImportError:
        pass

    try:
        from aurora_ext.rag.storage.postgres_kv import PostgresKVStorage

        _STORAGE_TYPE_MAP["kv"]["postgres"] = PostgresKVStorage
    except ImportError:
        pass

    # ── Vector backends ──────────────────────────────────────
    try:
        from aurora_ext.rag.storage.chroma_vector import ChromaVectorStorage

        _STORAGE_TYPE_MAP["vector"]["chroma"] = ChromaVectorStorage
    except ImportError:
        pass

    try:
        from aurora_ext.rag.storage.milvus_vector import MilvusVectorStorage

        _STORAGE_TYPE_MAP["vector"]["milvus"] = MilvusVectorStorage
    except ImportError:
        pass

    # ── Graph backends ───────────────────────────────────────
    try:
        from aurora_ext.rag.storage.networkx_graph import NetworkXGraphStorage

        _STORAGE_TYPE_MAP["graph"]["networkx"] = NetworkXGraphStorage
    except ImportError:
        pass

    try:
        from aurora_ext.rag.storage.neo4j_graph import Neo4jGraphStorage

        _STORAGE_TYPE_MAP["graph"]["neo4j"] = Neo4jGraphStorage
    except ImportError:
        pass

    # ── DocStatus backends ───────────────────────────────────
    try:
        from aurora_ext.rag.storage.json_doc_status import (
            JsonDocStatusStorage,
        )

        _STORAGE_TYPE_MAP["doc_status"]["json"] = JsonDocStatusStorage
    except ImportError:
        pass

    try:
        from aurora_ext.rag.storage.postgres_doc_status import (
            PostgresDocStatusStorage,
        )

        _STORAGE_TYPE_MAP["doc_status"]["postgres"] = (
            PostgresDocStatusStorage
        )
    except ImportError:
        pass


# Run registration at import time
_register_builtins()


class StorageFactory:
    """Factory for creating storage backend instances.

    Usage::

        factory = StorageFactory()
        kv_store = factory.create("kv", "postgres", "my_namespace", config)
    """

    _registry: dict[str, dict[str, type]] = _STORAGE_TYPE_MAP

    @classmethod
    def register(cls, storage_type: str, name: str, storage_cls: type) -> None:
        """Register a custom storage backend.

        Parameters
        ----------
        storage_type:
            One of ``"kv"``, ``"vector"``, ``"graph"``, ``"doc_status"``.
        name:
            Short backend name (e.g. ``"redis"``, ``"pinecone"``).
        storage_cls:
            The storage class to register.
        """
        if storage_type not in cls._registry:
            cls._registry[storage_type] = {}
        cls._registry[storage_type][name] = storage_cls

    @classmethod
    def create(
        cls,
        storage_type: str,
        backend: str,
        namespace: str,
        config: dict[str, Any],
    ) -> Any:
        """Create a storage instance by type and backend name.

        Parameters
        ----------
        storage_type:
            One of ``"kv"``, ``"vector"``, ``"graph"``, ``"doc_status"``.
        backend:
            Backend name (e.g. ``"json"``, ``"postgres"``, ``"neo4j"``).
        namespace:
            Storage namespace (table/collection/file prefix).
        config:
            Global configuration dict passed to the storage constructor.

        Returns
        -------
        An instance of the requested storage class.

        Raises
        ------
        ValueError
            If *storage_type* or *backend* is not registered.
        """
        type_map = cls._registry.get(storage_type)
        if type_map is None:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unknown storage type '{storage_type}'. "
                f"Available: {available}"
            )

        storage_cls = type_map.get(backend)
        if storage_cls is None:
            available = ", ".join(sorted(type_map.keys()))
            raise ValueError(
                f"Unknown backend '{backend}' for storage type "
                f"'{storage_type}'. Available: {available}"
            )

        return storage_cls(namespace, config)

    @classmethod
    def available_backends(cls, storage_type: str) -> list[str]:
        """Return registered backend names for a storage type."""
        type_map = cls._registry.get(storage_type, {})
        return sorted(type_map.keys())
