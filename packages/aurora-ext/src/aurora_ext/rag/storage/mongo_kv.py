"""MongoDB-backed key-value storage.

Production-grade KV store using ``motor`` (async MongoDB driver).
Each namespace maps to a collection ``kv_{namespace}`` within the
``aurora_rag`` database.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseKVStorage

logger = logging.getLogger(__name__)


class MongoKVStorage(BaseKVStorage):
    """MongoDB-backed key-value store."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)

        uri = (
            global_config.get("mongo_uri")
            or os.environ.get("AURORA_MONGO_URI")
            or "mongodb://localhost:27017"
        )
        db_name = global_config.get("mongo_db", "aurora_rag")

        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]
        self._collection = self._db[f"kv_{namespace}"]

    # ── BaseKVStorage interface ──────────────────────────────────

    async def all_keys(self) -> list[str]:
        cursor = self._collection.find({}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        doc = await self._collection.find_one({"_id": key})
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    async def get_by_ids(
        self, keys: list[str]
    ) -> list[Optional[dict[str, Any]]]:
        if not keys:
            return []
        cursor = self._collection.find({"_id": {"$in": keys}})
        lookup: dict[str, dict[str, Any]] = {}
        async for doc in cursor:
            doc_id = doc.pop("_id", None)
            if doc_id:
                lookup[doc_id] = doc
        return [lookup.get(k) for k in keys]

    async def get_by_field(
        self, field: str, value: Any
    ) -> list[dict[str, Any]]:
        cursor = self._collection.find({field: value})
        out: list[dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            out.append(doc)
        return out

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        from pymongo import UpdateOne

        operations: list[UpdateOne] = []
        for key, record in data.items():
            operations.append(
                UpdateOne(
                    {"_id": key},
                    {"$set": record},
                    upsert=True,
                )
            )
        await self._collection.bulk_write(operations)

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        await self._collection.delete_many({"_id": {"$in": keys}})

    async def drop(self) -> None:
        await self._collection.drop()
