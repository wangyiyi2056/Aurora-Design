"""MongoDB Atlas Vector Search-backed vector storage.

Uses ``motor`` (async MongoDB driver) with the Atlas Vector Search
``$vectorSearch`` aggregation pipeline stage.

.. note::
   Atlas Vector Search requires a specific search index configured
   on the MongoDB Atlas cluster. The index must map the ``embedding``
   field with ``numDimensions`` matching the embedding dimension.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseVectorStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


class MongoVectorDBStorage(BaseVectorStorage):
    """MongoDB Atlas Vector Search-backed vector storage.

    Supports workspace isolation via collection name prefixing.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)

        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm

        self._embedding_func = global_config.get("embedding_func")

        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

        uri = (
            global_config.get("mongo_uri")
            or os.environ.get("AURORA_MONGO_URI")
            or "mongodb://localhost:27017"
        )
        db_name = global_config.get("mongo_db", "aurora_rag")
        self._vector_search_index = global_config.get(
            "mongo_vector_index", "vector_index"
        )

        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]
        coll_name = wm.get_collection_name(f"vector_{namespace}")
        self._collection = self._db[coll_name]

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return

        from pymongo import UpdateOne

        operations: list[UpdateOne] = []
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
                "content": content,
                "embedding": [float(x) for x in vec],
                "metadata": meta,
            }
            operations.append(
                UpdateOne({"_id": key}, {"$set": doc}, upsert=True)
            )

        if operations:
            await self._collection.bulk_write(operations)

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        if self._embedding_func is None:
            logger.warning("No embedding function; cannot perform vector query")
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_vec = vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])

        vector_search: dict[str, Any] = {
            "index": self._vector_search_index,
            "path": "embedding",
            "queryVector": [float(x) for x in query_vec],
            "numCandidates": top_k * 10,
            "limit": top_k,
        }
        if where:
            vector_search["filter"] = {f"metadata.{k}": v for k, v in where.items()}

        pipeline = [
            {"$vectorSearch": vector_search},
            {
                "$project": {
                    "_id": 1,
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        cursor = self._collection.aggregate(pipeline)
        out: list[dict[str, Any]] = []
        async for doc in cursor:
            score = doc.get("score", 0.0)
            if score < cosine_threshold:
                continue
            record: dict[str, Any] = {
                "id": str(doc["_id"]),
                "score": score,
                "content": doc.get("content", ""),
            }
            metadata = doc.get("metadata", {})
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
        await self._collection.delete_many({"_id": {"$in": ids}})

    async def drop(self) -> None:
        await self._collection.drop()
