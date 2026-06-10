"""MongoDB-backed document status storage.

Production-grade document status tracker using ``motor`` (async
MongoDB driver).  Each namespace maps to a collection
``doc_status_{namespace}`` within the ``aurora_rag`` database.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from aurora_ext.rag.storage.base import (
    BaseDocStatusStorage,
    DocStatus,
    DocStatusInfo,
)
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MongoDocStatusStorage(BaseDocStatusStorage):
    """MongoDB-backed document status storage.

    Supports workspace isolation via collection name prefixing.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)

        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm

        uri = (
            global_config.get("mongo_uri")
            or os.environ.get("AURORA_MONGO_URI")
            or "mongodb://localhost:27017"
        )
        db_name = global_config.get("mongo_db", "aurora_rag")

        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]
        coll_name = wm.get_collection_name(f"doc_status_{namespace}")
        self._collection = self._db[coll_name]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._collection.create_index("status")
        await self._collection.create_index([("kb_name", 1), ("status", 1)])
        await self._collection.create_index([("kb_name", 1), ("content_hash", 1)])
        await self._collection.create_index([("kb_name", 1), ("basename", 1)])
        await self._collection.create_index("track_id")
        await self._collection.create_index("created_at")
        self._indexes_ready = True

    @staticmethod
    def _to_info(raw: dict[str, Any]) -> DocStatusInfo:
        """Convert a MongoDB document to a :class:`DocStatusInfo`."""
        metadata = raw.get("metadata", {})
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)
        return DocStatusInfo(
            id=raw.get("_id", raw.get("id", "")),
            file_path=raw.get("file_path", ""),
            status=DocStatus(raw.get("status", "PENDING")),
            content_summary=raw.get("content_summary", ""),
            content_length=raw.get("content_length", 0),
            chunks_count=raw.get("chunks_count", 0),
            error_msg=raw.get("error_msg"),
            track_id=raw.get("track_id", ""),
            metadata=metadata,
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
            kb_name=raw.get("kb_name", ""),
            content_hash=raw.get("content_hash", ""),
            duplicate_kind=raw.get("duplicate_kind", ""),
            basename=raw.get("basename", ""),
        )

    @staticmethod
    def _matches_kb(raw: dict[str, Any], kb_name: str | None) -> bool:
        if not kb_name:
            return True
        return raw.get("kb_name", "") == kb_name

    def _kb_filter(self, kb_name: str | None) -> dict[str, Any]:
        """Return a MongoDB filter for kb_name scoping."""
        if not kb_name:
            return {}
        return {"kb_name": kb_name}

    # ── BaseDocStatusStorage interface ───────────────────────────

    async def get_status(self, doc_id: str) -> Optional[DocStatusInfo]:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"_id": doc_id})
        if doc is None:
            return None
        return self._to_info(doc)

    async def get_statuses_by_ids(
        self, doc_ids: list[str]
    ) -> list[Optional[DocStatusInfo]]:
        if not doc_ids:
            return []
        await self._ensure_indexes()
        cursor = self._collection.find({"_id": {"$in": doc_ids}})
        lookup: dict[str, DocStatusInfo] = {}
        async for doc in cursor:
            info = self._to_info(doc)
            lookup[info.id] = info
        return [lookup.get(did) for did in doc_ids]

    async def get_docs_by_status(
        self, status: DocStatus, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        await self._ensure_indexes()
        query: dict[str, Any] = {"status": status.value, **self._kb_filter(kb_name)}
        cursor = self._collection.find(query)
        return [self._to_info(doc) async for doc in cursor]

    async def get_all_docs(
        self,
        status_filters: Optional[list[DocStatus]] = None,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "created_at",
        sort_direction: str = "desc",
        *,
        kb_name: str | None = None,
    ) -> tuple[list[DocStatusInfo], int]:
        await self._ensure_indexes()

        query: dict[str, Any] = {**self._kb_filter(kb_name)}
        if status_filters:
            query["status"] = {"$in": [s.value for s in status_filters]}

        total = await self._collection.count_documents(query)

        pymongo_sort_dir = -1 if sort_direction == "desc" else 1
        cursor = (
            self._collection.find(query)
            .sort(sort_field, pymongo_sort_dir)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        docs = [self._to_info(doc) async for doc in cursor]
        return docs, total

    async def get_status_counts(
        self, *, kb_name: str | None = None
    ) -> dict[str, int]:
        await self._ensure_indexes()
        match_stage: dict[str, Any] = {**self._kb_filter(kb_name)}
        pipeline: list[dict[str, Any]] = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({"$group": {"_id": "$status", "count": {"$sum": 1}}})

        cursor = self._collection.aggregate(pipeline)
        counts: dict[str, int] = {}
        async for doc in cursor:
            status_val = doc["_id"]
            counts[status_val] = doc["count"]
        return counts

    async def upsert(self, docs: dict[str, DocStatusInfo]) -> None:
        if not docs:
            return
        await self._ensure_indexes()
        now = _now_iso()

        from pymongo import UpdateOne

        operations: list[UpdateOne] = []
        for doc_id, info in docs.items():
            record = asdict(info)
            record["status"] = info.status.value

            # Check existing for created_at preservation
            existing = await self._collection.find_one(
                {"_id": doc_id}, {"created_at": 1}
            )
            if existing is None:
                record["created_at"] = now
            else:
                record["created_at"] = existing.get("created_at", now)
            record["updated_at"] = now

            # Remove 'id' field since we use _id
            record.pop("id", None)
            operations.append(
                UpdateOne(
                    {"_id": doc_id},
                    {"$set": record},
                    upsert=True,
                )
            )

        await self._collection.bulk_write(operations)

    async def update_status(
        self,
        doc_id: str,
        status: DocStatus,
        error_msg: Optional[str] = None,
        **extra: Any,
    ) -> None:
        await self._ensure_indexes()
        now = _now_iso()
        update: dict[str, Any] = {
            "status": status.value,
            "updated_at": now,
        }
        if error_msg is not None:
            update["error_msg"] = error_msg
        for k, v in extra.items():
            update[k] = v

        await self._collection.update_one(
            {"_id": doc_id},
            {
                "$set": update,
                "$setOnInsert": {"created_at": now, "file_path": ""},
            },
            upsert=True,
        )

    async def get_doc_by_basename(
        self, basename: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        await self._ensure_indexes()
        query: dict[str, Any] = {
            "basename": basename,
            **self._kb_filter(kb_name),
        }
        doc = await self._collection.find_one(query)
        if doc is None:
            return None
        return self._to_info(doc)

    async def get_doc_by_content_hash(
        self, content_hash: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        await self._ensure_indexes()
        query: dict[str, Any] = {
            "content_hash": content_hash,
            **self._kb_filter(kb_name),
        }
        doc = await self._collection.find_one(query)
        if doc is None:
            return None
        return self._to_info(doc)

    async def delete(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        await self._ensure_indexes()
        await self._collection.delete_many({"_id": {"$in": doc_ids}})

    async def drop(self) -> None:
        await self._collection.drop()
