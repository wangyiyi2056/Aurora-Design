"""OpenSearch k-NN-backed vector storage.

Production-grade vector store using ``opensearch-py[async]`` with the
k-NN plugin for HNSW-based cosine similarity search.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseVectorStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


def _sanitize_index_name(namespace: str) -> str:
    """Convert namespace to a valid OpenSearch index name."""
    sanitized = re.sub(r"[^a-z0-9_\\-]", "_", namespace.lower())
    return f"aurora_vector_{sanitized}"


class OpenSearchVectorDBStorage(BaseVectorStorage):
    """OpenSearch k-NN-backed vector storage with HNSW indexing.

    Supports workspace isolation via index name prefixing.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        ws_ns = wm.get_collection_name(namespace)
        self._index = _sanitize_index_name(ws_ns)

        self._embedding_func = global_config.get("embedding_func")

        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

        uri = (
            global_config.get("opensearch_uri")
            or os.environ.get("AURORA_OPENSEARCH_URI")
            or "https://localhost:9200"
        )
        username = global_config.get("opensearch_user", "admin")
        password = global_config.get("opensearch_password", "admin")
        verify_certs = global_config.get("opensearch_verify_certs", False)

        from opensearchpy import AsyncOpenSearch

        self._client = AsyncOpenSearch(
            hosts=[uri],
            http_auth=(username, password),
            verify_certs=verify_certs,
            ssl_show_warn=False,
        )
        self._index_ready = False

    async def _ensure_index(self) -> None:
        if self._index_ready:
            return
        exists = await self._client.indices.exists(index=self._index)
        if not exists:
            body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 128,
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    }
                },
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self._embedding_dim,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 16,
                                },
                            },
                        },
                        "content": {"type": "text"},
                        "metadata": {"type": "object", "enabled": True},
                    }
                },
            }
            await self._client.indices.create(index=self._index, body=body)
        self._index_ready = True

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        await self._ensure_index()

        body: list[dict[str, Any]] = []
        for key, record in data.items():
            vector = record.get("__vector__")
            if vector is None:
                logger.warning("Record %s missing __vector__, skipping", key)
                continue

            vec = vector if isinstance(vector, list) else list(vector)
            content = record.get("content", "")
            meta = {
                k: v
                for k, v in record.items()
                if k not in ("content", "__vector__")
            }

            doc: dict[str, Any] = {
                "embedding": [float(x) for x in vec],
                "content": content,
                "metadata": meta,
            }
            body.append({"index": {"_index": self._index, "_id": key}})
            body.append(doc)

        if body:
            await self._client.bulk(body=body, refresh="wait_for")

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        await self._ensure_index()

        if self._embedding_func is None:
            logger.warning("No embedding function; cannot perform vector query")
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_vec = vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])

        resp = await self._client.search(
            index=self._index,
            body={
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": [float(x) for x in query_vec],
                            "k": top_k,
                        }
                    }
                },
                "_source": ["content", "metadata"],
            },
        )

        out: list[dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            score = hit.get("_score", 0.0)
            if score < cosine_threshold:
                continue

            source = hit.get("_source", {})
            record: dict[str, Any] = {
                "id": hit["_id"],
                "score": score,
                "content": source.get("content", ""),
            }
            metadata = source.get("metadata", {})
            if isinstance(metadata, dict):
                record.update(metadata)
            out.append(record)

        return out

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        await self._ensure_index()
        body: list[dict[str, Any]] = []
        for doc_id in ids:
            body.append({"delete": {"_index": self._index, "_id": doc_id}})
        if body:
            await self._client.bulk(body=body, refresh="wait_for")

    async def drop(self) -> None:
        try:
            exists = await self._client.indices.exists(index=self._index)
            if exists:
                await self._client.indices.delete(index=self._index)
            self._index_ready = False
        except Exception as exc:
            logger.warning("Failed to drop index %s: %s", self._index, exc)
