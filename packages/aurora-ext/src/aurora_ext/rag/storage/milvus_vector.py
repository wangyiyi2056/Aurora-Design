"""Milvus-backed vector storage.

Production-grade vector store using ``pymilvus`` SDK with HNSW indexing
and cosine similarity.  Each namespace maps to a dedicated Milvus
collection.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseVectorStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


def _sanitize_collection_name(namespace: str) -> str:
    """Convert a namespace into a valid Milvus collection name.

    Milvus collection names must start with a letter or underscore and
    contain only alphanumeric characters and underscores.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", namespace)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != "_":
        sanitized = f"_{sanitized}"
    name = f"aurora_{sanitized}"
    # Milvus max collection name length is 255
    return name[:255]


class MilvusVectorStorage(BaseVectorStorage):
    """Milvus-backed vector storage with HNSW indexing.

    Supports workspace isolation: when a ``WorkspaceManager`` is present
    in ``global_config``, the collection name is prefixed with the
    workspace ID to isolate vector data per tenant.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)

        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        ws_namespace = wm.get_collection_name(namespace)
        self._collection_name = _sanitize_collection_name(ws_namespace)
        self._embedding_func = global_config.get("embedding_func")

        # Determine embedding dimension
        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

        uri = (
            global_config.get("milvus_uri")
            or os.environ.get("AURORA_MILVUS_URI")
            or "http://localhost:19530"
        )
        token = (
            global_config.get("milvus_token")
            or os.environ.get("AURORA_MILVUS_TOKEN")
            or ""
        )

        from pymilvus import Collection, connections, utility

        self._connections = connections
        self._utility = utility
        self._Collection = Collection

        conn_kwargs: dict[str, Any] = {"uri": uri}
        if token:
            conn_kwargs["token"] = token

        self._connections.connect(alias="default", **conn_kwargs)
        self._collection: Optional[Collection] = None

    def _ensure_collection(self) -> None:
        """Create or load the Milvus collection."""
        if self._collection is not None:
            return

        from pymilvus import (
            CollectionSchema,
            DataType,
            FieldSchema,
        )

        if self._utility.has_collection(self._collection_name):
            self._collection = self._Collection(self._collection_name)
            self._collection.load()
            return

        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=256,
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self._embedding_dim,
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=65535,
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON,
            ),
        ]
        schema = CollectionSchema(
            fields=fields, description=self.namespace
        )
        self._collection = self._Collection(
            name=self._collection_name, schema=schema
        )

        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256},
        }
        self._collection.create_index(
            field_name="embedding", index_params=index_params
        )
        self._collection.load()

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        self._ensure_collection()
        assert self._collection is not None

        ids: list[str] = []
        embeddings: list[list[float]] = []
        contents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for key, record in data.items():
            ids.append(key)
            content = record.get("content", "")
            contents.append(content)

            vector = record.get("__vector__")
            if vector is not None:
                embeddings.append(
                    vector if isinstance(vector, list) else list(vector)
                )
            else:
                # Placeholder — caller should provide vectors
                embeddings.append([0.0] * self._embedding_dim)

            meta = {
                k: v
                for k, v in record.items()
                if k not in ("content", "__vector__")
            }
            metadatas.append(meta)

        # Delete existing records first (upsert semantics)
        try:
            expr = f'id in [{", ".join(repr(i) for i in ids)}]'
            self._collection.delete(expr)
        except Exception:
            pass  # Some IDs may not exist yet

        self._collection.insert(
            data=[ids, embeddings, contents, metadatas],
        )
        self._collection.flush()

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        self._ensure_collection()
        assert self._collection is not None

        if self._embedding_func is None:
            logger.warning(
                "No embedding function configured; "
                "cannot perform vector query"
            )
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_embedding = (
            vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])
        )

        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": max(top_k * 2, 128)},
        }

        results = self._collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["content", "metadata"],
        )

        out: list[dict[str, Any]] = []
        if results and len(results) > 0:
            for hit in results[0]:
                score = hit.score
                if score < cosine_threshold:
                    continue

                record: dict[str, Any] = {
                    "id": hit.id,
                    "score": score,
                }

                entity = hit.entity
                content = entity.get("content", "")
                if content:
                    record["content"] = content

                metadata = entity.get("metadata", {})
                if isinstance(metadata, dict):
                    record.update(metadata)

                out.append(record)

        if where:
            out = [
                r for r in out
                if all(r.get(k) == v for k, v in where.items())
            ]
        return out

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        self._ensure_collection()
        assert self._collection is not None

        try:
            expr = f'id in [{", ".join(repr(i) for i in ids)}]'
            self._collection.delete(expr)
            self._collection.flush()
        except Exception as exc:
            logger.warning("Failed to delete vectors: %s", exc)

    async def drop(self) -> None:
        try:
            if self._utility.has_collection(self._collection_name):
                self._utility.drop_collection(self._collection_name)
            self._collection = None
        except Exception as exc:
            logger.warning(
                "Failed to drop collection %s: %s",
                self._collection_name,
                exc,
            )
