"""OpenSearch-backed document status storage.

Production-grade document status tracker using ``opensearch-py[async]``.
Each namespace maps to an index ``aurora_doc_status_{namespace}``.
"""

from __future__ import annotations

import json
import logging
import os
import re
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


def _sanitize_index_name(namespace: str) -> str:
    """Convert namespace to a valid OpenSearch index name."""
    sanitized = re.sub(r"[^a-z0-9_\\-]", "_", namespace.lower())
    return f"aurora_doc_status_{sanitized}"


_INDEX_MAPPING = {
    "properties": {
        "status": {"type": "keyword"},
        "file_path": {"type": "text"},
        "content_summary": {"type": "text"},
        "content_length": {"type": "integer"},
        "chunks_count": {"type": "integer"},
        "error_msg": {"type": "text"},
        "track_id": {"type": "keyword"},
        "kb_name": {"type": "keyword"},
        "content_hash": {"type": "keyword"},
        "duplicate_kind": {"type": "keyword"},
        "basename": {"type": "keyword"},
        "metadata": {"type": "object", "enabled": True},
        "created_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
        "updated_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
    }
}


class OpenSearchDocStatusStorage(BaseDocStatusStorage):
    """OpenSearch-backed document status storage.

    Supports workspace isolation via index name prefixing.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        ws_ns = wm.get_collection_name(namespace)
        self._index = _sanitize_index_name(ws_ns)

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
            await self._client.indices.create(
                index=self._index,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    },
                    "mappings": _INDEX_MAPPING,
                },
            )
        self._index_ready = True

    @staticmethod
    def _to_info(source: dict[str, Any], doc_id: str = "") -> DocStatusInfo:
        """Convert an OpenSearch source document to a :class:`DocStatusInfo`."""
        metadata = source.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return DocStatusInfo(
            id=doc_id or source.get("id", ""),
            file_path=source.get("file_path", ""),
            status=DocStatus(source.get("status", "PENDING")),
            content_summary=source.get("content_summary", ""),
            content_length=source.get("content_length", 0),
            chunks_count=source.get("chunks_count", 0),
            error_msg=source.get("error_msg"),
            track_id=source.get("track_id", ""),
            metadata=metadata,
            created_at=str(source.get("created_at", "")),
            updated_at=str(source.get("updated_at", "")),
            kb_name=source.get("kb_name", ""),
            content_hash=source.get("content_hash", ""),
            duplicate_kind=source.get("duplicate_kind", ""),
            basename=source.get("basename", ""),
        )

    def _kb_filter(self, kb_name: str | None) -> dict[str, Any]:
        """Return an OpenSearch filter clause for kb_name scoping."""
        if not kb_name:
            return {}
        return {"term": {"kb_name": kb_name}}

    def _build_query(
        self,
        *,
        kb_name: str | None = None,
        status_filters: Optional[list[DocStatus]] = None,
        extra_must: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Build an OpenSearch bool query with optional filters."""
        must: list[dict[str, Any]] = extra_must or []
        if status_filters:
            must.append({
                "terms": {"status": [s.value for s in status_filters]}
            })

        kb = self._kb_filter(kb_name)
        if kb:
            must.append(kb)

        if not must:
            return {"match_all": {}}
        if len(must) == 1:
            return must[0]
        return {"bool": {"must": must}}

    # ── BaseDocStatusStorage interface ───────────────────────────

    async def get_status(self, doc_id: str) -> Optional[DocStatusInfo]:
        await self._ensure_index()
        try:
            resp = await self._client.get(index=self._index, id=doc_id)
            source = resp.get("_source", {})
            return self._to_info(source, doc_id=resp["_id"])
        except Exception:
            return None

    async def get_statuses_by_ids(
        self, doc_ids: list[str]
    ) -> list[Optional[DocStatusInfo]]:
        if not doc_ids:
            return []
        await self._ensure_index()
        resp = await self._client.mget(index=self._index, body={"ids": doc_ids})
        lookup: dict[str, DocStatusInfo] = {}
        for doc in resp.get("docs", []):
            if doc.get("found"):
                info = self._to_info(doc.get("_source", {}), doc_id=doc["_id"])
                lookup[info.id] = info
        return [lookup.get(did) for did in doc_ids]

    async def get_docs_by_status(
        self, status: DocStatus, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        await self._ensure_index()
        query = self._build_query(
            kb_name=kb_name,
            status_filters=[status],
        )
        resp = await self._client.search(
            index=self._index,
            body={"query": query, "size": 10000},
        )
        return [
            self._to_info(hit["_source"], doc_id=hit["_id"])
            for hit in resp.get("hits", {}).get("hits", [])
        ]

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
        await self._ensure_index()

        allowed_sort = {
            "created_at", "updated_at", "status", "file_path",
            "content_length", "chunks_count", "kb_name",
        }
        if sort_field not in allowed_sort:
            sort_field = "created_at"
        order = "desc" if sort_direction == "desc" else "asc"

        query = self._build_query(
            kb_name=kb_name,
            status_filters=status_filters,
        )

        resp = await self._client.search(
            index=self._index,
            body={
                "query": query,
                "sort": [{sort_field: {"order": order}}],
                "from": (page - 1) * page_size,
                "size": page_size,
            },
        )

        total = resp.get("hits", {}).get("total", {}).get("value", 0)
        docs = [
            self._to_info(hit["_source"], doc_id=hit["_id"])
            for hit in resp.get("hits", {}).get("hits", [])
        ]
        return docs, total

    async def get_status_counts(
        self, *, kb_name: str | None = None
    ) -> dict[str, int]:
        await self._ensure_index()
        kb = self._kb_filter(kb_name)
        query: dict[str, Any] = {"match_all": {}}
        if kb:
            query = {"bool": {"filter": [kb]}}

        resp = await self._client.search(
            index=self._index,
            body={
                "size": 0,
                "query": query,
                "aggs": {
                    "status_counts": {
                        "terms": {"field": "status", "size": 20}
                    }
                },
            },
        )
        buckets = (
            resp.get("aggregations", {})
            .get("status_counts", {})
            .get("buckets", [])
        )
        return {b["key"]: b["doc_count"] for b in buckets}

    async def upsert(self, docs: dict[str, DocStatusInfo]) -> None:
        if not docs:
            return
        await self._ensure_index()
        now = _now_iso()

        from dataclasses import asdict

        body: list[dict[str, Any]] = []
        for doc_id, info in docs.items():
            record = asdict(info)
            record["status"] = info.status.value

            # Preserve created_at for existing docs
            existing = await self.get_status(doc_id)
            if existing is None:
                record["created_at"] = now
            else:
                record["created_at"] = existing.created_at or now
            record["updated_at"] = now

            record.pop("id", None)
            body.append({"index": {"_index": self._index, "_id": doc_id}})
            body.append(record)

        if body:
            await self._client.bulk(body=body, refresh="wait_for")

    async def update_status(
        self,
        doc_id: str,
        status: DocStatus,
        error_msg: Optional[str] = None,
        **extra: Any,
    ) -> None:
        await self._ensure_index()
        now = _now_iso()
        update: dict[str, Any] = {
            "status": status.value,
            "updated_at": now,
        }
        if error_msg is not None:
            update["error_msg"] = error_msg
        for k, v in extra.items():
            update[k] = v

        # Use scripted update to handle upsert
        try:
            await self._client.update(
                index=self._index,
                id=doc_id,
                body={
                    "doc": update,
                    "doc_as_upsert": True,
                },
                refresh="wait_for",
            )
        except Exception:
            # Fallback: index with defaults
            update.setdefault("created_at", now)
            update.setdefault("file_path", "")
            await self._client.index(
                index=self._index, id=doc_id, body=update, refresh="wait_for"
            )

    async def get_doc_by_basename(
        self, basename: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        await self._ensure_index()
        must: list[dict[str, Any]] = [{"term": {"basename": basename}}]
        kb = self._kb_filter(kb_name)
        if kb:
            must.append(kb)

        resp = await self._client.search(
            index=self._index,
            body={"query": {"bool": {"must": must}}, "size": 1},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return self._to_info(hits[0]["_source"], doc_id=hits[0]["_id"])

    async def get_doc_by_content_hash(
        self, content_hash: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        await self._ensure_index()
        must: list[dict[str, Any]] = [{"term": {"content_hash": content_hash}}]
        kb = self._kb_filter(kb_name)
        if kb:
            must.append(kb)

        resp = await self._client.search(
            index=self._index,
            body={"query": {"bool": {"must": must}}, "size": 1},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return self._to_info(hits[0]["_source"], doc_id=hits[0]["_id"])

    async def delete(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        await self._ensure_index()
        body: list[dict[str, Any]] = []
        for doc_id in doc_ids:
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
