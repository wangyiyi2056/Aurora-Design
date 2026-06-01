"""Abstract base classes for the four RAG storage types.

Migrated from LightRAG ``base.py``.  Each storage type is independent
and can be backed by different concrete implementations (JSON files,
ChromaDB, NetworkX, PostgreSQL, Neo4j, etc.).
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Document processing status ───────────────────────────────────


class DocStatus(str, enum.Enum):
    """State machine for document processing lifecycle."""

    PENDING = "PENDING"
    PARSING = "PARSING"
    ANALYZING = "ANALYZING"
    PREPROCESSED = "PREPROCESSED"  # backward compat
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclass
class DocStatusInfo:
    """Metadata for a single document's processing state."""

    id: str
    file_path: str
    status: DocStatus = DocStatus.PENDING
    content_summary: str = ""
    content_length: int = 0
    chunks_count: int = 0
    error_msg: Optional[str] = None
    track_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    kb_name: str = ""
    content_hash: str = ""
    duplicate_kind: str = ""
    basename: str = ""


# ── Base mixin ───────────────────────────────────────────────────


class StorageNameSpace(ABC):
    """Mixin that associates a storage instance with a namespace."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        self.namespace = namespace
        self.global_config = global_config


# ── KV Storage ───────────────────────────────────────────────────


class BaseKVStorage(StorageNameSpace, ABC):
    """Key-value storage for documents, chunks, entities, relations, cache."""

    @abstractmethod
    async def all_keys(self) -> list[str]:
        """Return all keys in this namespace."""

    @abstractmethod
    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        """Get a single record by key."""

    @abstractmethod
    async def get_by_ids(self, keys: list[str]) -> list[Optional[dict[str, Any]]]:
        """Batch-get records by keys.  Missing keys return ``None``."""

    @abstractmethod
    async def get_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        """Get all records where *field* == *value*."""

    @abstractmethod
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """Insert or update multiple records.

        *data* maps key → record dict.
        """

    @abstractmethod
    async def delete(self, keys: list[str]) -> None:
        """Delete records by keys.

        Silently ignores keys that do not exist.
        """

    @abstractmethod
    async def drop(self) -> None:
        """Drop all data in this namespace."""


# ── Vector Storage ───────────────────────────────────────────────


class BaseVectorStorage(StorageNameSpace, ABC):
    """Vector storage for entity / relation / chunk embeddings."""

    @abstractmethod
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """Insert or update vectors.

        Each value in *data* must contain:
        - ``content``: the original text
        - ``__vector__``: pre-computed embedding (optional; some backends
          compute internally)
        - any additional metadata fields
        """

    @abstractmethod
    async def query(
        self,
        query: str,
        top_k: int,
        cosine_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search by query string embedding, return top-k results.

        Results should include ``id``, ``content``, ``score``, and all
        metadata fields.  Only results with ``score >= cosine_threshold``
        are returned.
        """

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs."""

    @abstractmethod
    async def drop(self) -> None:
        """Drop all data in this namespace."""


# ── Graph Storage ────────────────────────────────────────────────


class BaseGraphStorage(StorageNameSpace, ABC):
    """Graph storage for the knowledge graph (entities + relationships)."""

    # ── Node (entity) operations ─────────────────────────────────

    @abstractmethod
    async def has_node(self, node_id: str) -> bool:
        """Check if a node exists."""

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        """Get node properties."""

    @abstractmethod
    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        """Insert or update a node."""

    @abstractmethod
    async def delete_node(self, node_id: str) -> None:
        """Delete a node and all its edges."""

    @abstractmethod
    async def node_degree(self, node_id: str) -> int:
        """Return the number of edges connected to *node_id*."""

    @abstractmethod
    async def get_all_labels(self) -> list[str]:
        """Return all node labels (entity names)."""

    @abstractmethod
    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        """Return labels ordered by node degree (descending)."""

    @abstractmethod
    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        """Fuzzy-search labels by *query* substring."""

    # ── Edge (relationship) operations ───────────────────────────

    @abstractmethod
    async def has_edge(self, source_id: str, target_id: str) -> bool:
        """Check if an edge exists."""

    @abstractmethod
    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        """Get edge properties."""

    @abstractmethod
    async def upsert_edge(
        self, source_id: str, target_id: str, edge_data: dict[str, Any]
    ) -> None:
        """Insert or update an edge."""

    @abstractmethod
    async def delete_edge(self, source_id: str, target_id: str) -> None:
        """Delete an edge."""

    @abstractmethod
    async def edge_degree(self, source_id: str, target_id: str) -> int:
        """Return edge weight or degree metric."""

    # ── Traversal operations ─────────────────────────────────────

    @abstractmethod
    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        """Return all (source, target) edges connected to *node_id*."""

    @abstractmethod
    async def get_neighbors(self, node_id: str) -> list[str]:
        """Return IDs of all nodes connected to *node_id*."""

    @abstractmethod
    async def get_connected_subgraph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """Return a subgraph starting from *label* with BFS traversal.

        Returns ``{"nodes": [...], "edges": [...]}``.
        """

    # ── Bulk operations ──────────────────────────────────────────

    @abstractmethod
    async def get_all_nodes(self) -> list[dict[str, Any]]:
        """Return all nodes with their properties."""

    @abstractmethod
    async def get_all_edges(self) -> list[dict[str, Any]]:
        """Return all edges with their properties."""

    @abstractmethod
    async def drop(self) -> None:
        """Drop all data in this namespace."""


# ── Document Status Storage ──────────────────────────────────────


class BaseDocStatusStorage(StorageNameSpace, ABC):
    """Tracks document processing state across the pipeline."""

    @abstractmethod
    async def get_status(self, doc_id: str) -> Optional[DocStatusInfo]:
        """Get the status of a single document."""

    @abstractmethod
    async def get_statuses_by_ids(self, doc_ids: list[str]) -> list[Optional[DocStatusInfo]]:
        """Batch-get document statuses."""

    @abstractmethod
    async def get_docs_by_status(
        self, status: DocStatus, *, kb_name: Optional[str] = None
    ) -> list[DocStatusInfo]:
        """Return all documents with the given status.

        If *kb_name* is provided, only documents belonging to that knowledge
        base are returned.
        """

    @abstractmethod
    async def get_all_docs(
        self,
        status_filters: Optional[list[DocStatus]] = None,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "created_at",
        sort_direction: str = "desc",
        *,
        kb_name: Optional[str] = None,
    ) -> tuple[list[DocStatusInfo], int]:
        """Paginated document listing with optional status filters.

        If *kb_name* is provided, only documents belonging to that knowledge
        base are returned.  Returns ``(docs, total_count)``.
        """

    @abstractmethod
    async def get_status_counts(self, *, kb_name: Optional[str] = None) -> dict[str, int]:
        """Return counts grouped by status.

        If *kb_name* is provided, only counts for that knowledge base are returned.
        """

    @abstractmethod
    async def upsert(self, docs: dict[str, DocStatusInfo]) -> None:
        """Insert or update document statuses."""

    @abstractmethod
    async def update_status(
        self,
        doc_id: str,
        status: DocStatus,
        error_msg: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Update a single document's status."""

    @abstractmethod
    async def get_doc_by_basename(
        self, basename: str, *, kb_name: Optional[str] = None
    ) -> Optional[DocStatusInfo]:
        """Find a document by its filename basename.

        Parameters
        ----------
        basename:
            The filename without directory path (e.g. ``"report.pdf"``).
        kb_name:
            When provided, only documents belonging to that knowledge base
            are considered.

        Returns
        -------
        Optional[DocStatusInfo]
            The first matching document, or ``None`` if not found.
        """

    @abstractmethod
    async def get_doc_by_content_hash(
        self, content_hash: str, *, kb_name: Optional[str] = None
    ) -> Optional[DocStatusInfo]:
        """Find a document by its content hash.

        Parameters
        ----------
        content_hash:
            The MD5-based content hash (as produced by
            :func:`compute_mdhash_id`).
        kb_name:
            When provided, only documents belonging to that knowledge base
            are considered.

        Returns
        -------
        Optional[DocStatusInfo]
            The first matching document, or ``None`` if not found.
        """

    @abstractmethod
    async def delete(self, doc_ids: list[str]) -> None:
        """Delete status records."""

    @abstractmethod
    async def drop(self) -> None:
        """Drop all status data."""
