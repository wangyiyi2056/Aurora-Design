"""Qdrant-backed vector storage.

Production-grade vector store using the ``qdrant-client`` async API
with HNSW indexing and cosine similarity.
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
    """Convert namespace to a valid Qdrant collection name."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", namespace)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != "_":
        sanitized = f"_{sanitized}"
    name = f"aurora_{sanitized}"
    return name[:255]


class QdrantVectorDBStorage(BaseVectorStorage):
    """Qdrant-backed vector storage with HNSW indexing.

    Supports workspace isolation via collection name prefixing.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)

        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        ws_ns = wm.get_collection_name(namespace)
        self._collection_name = _sanitize_collection_name(ws_ns)
        self._embedding_func = global_config.get("embedding_func")

        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

        uri = (
            global_config.get("qdrant_uri")
            or os.environ.get("AURORA_QDRANT_URI")
            or "http://localhost:6333"
        )
        api_key = global_config.get("qdrant_api_key") or os.environ.get(
            "AURORA_QDRANT_API_KEY"
        )

        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import (
            Distance,
            HnswConfigDiff,
            VectorParams,
        )

        self._Distance = Distance
        self._HnswConfigDiff = HnswConfigDiff
        self._VectorParams = VectorParams

        client_kwargs: dict[str, Any] = {"url": uri}
        if api_key:
            client_kwargs["api_key"] = api_key

        self._client = AsyncQdrantClient(**client_kwargs)
        self._collection_ready = False

    async def _ensure_collection(self) -> None:
        if self._collection_ready:
            return

        from qdrant_client.models import (
            Distance,
            HnswConfigDiff,
            VectorParams,
        )

        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}

        if self._collection_name not in existing:
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._embedding_dim,
                    distance=Distance.COSINE,
                ),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
            )
        self._collection_ready = True

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        await self._ensure_collection()

        from qdrant_client.models import PointStruct

        points: list[PointStruct] = []
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
            payload = {"content": content, **meta}

            # Qdrant requires UUID-like or int point IDs; use a hash-based int
            point_id = hash(key) & 0x7FFFFFFFFFFFFFFF
            points.append(
                PointStruct(id=point_id, vector=vec, payload=payload)
            )

        if points:
            await self._client.upsert(
                collection_name=self._collection_name, points=points
            )

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        await self._ensure_collection()

        if self._embedding_func is None:
            logger.warning("No embedding function; cannot perform vector query")
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_vec = vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])

        query_filter = None
        if where:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in where.items()
                ]
            )

        results = await self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vec,
            limit=top_k,
            with_payload=True,
            query_filter=query_filter,
        )

        out: list[dict[str, Any]] = []
        for hit in results:
            score = hit.score
            if score < cosine_threshold:
                continue

            payload = hit.payload or {}
            record: dict[str, Any] = {
                "id": str(hit.id),
                "score": score,
            }
            content = payload.pop("content", "")
            if content:
                record["content"] = content
            record.update(payload)
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
        await self._ensure_collection()

        from qdrant_client.models import PointIdsList

        point_ids = [hash(i) & 0x7FFFFFFFFFFFFFFF for i in ids]
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=point_ids),
        )

    async def drop(self) -> None:
        try:
            collections = await self._client.get_collections()
            existing = {c.name for c in collections.collections}
            if self._collection_name in existing:
                await self._client.delete_collection(
                    collection_name=self._collection_name
                )
            self._collection_ready = False
        except Exception as exc:
            logger.warning(
                "Failed to drop collection %s: %s",
                self._collection_name,
                exc,
            )
