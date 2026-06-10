"""OpenSearch-backed key-value storage.

Production-grade KV store using ``opensearch-py[async]``.
Each namespace maps to an index ``aurora_kv_{namespace}``.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseKVStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


def _sanitize_index_name(namespace: str) -> str:
    """Convert namespace to a valid OpenSearch index name."""
    sanitized = re.sub(r"[^a-z0-9_\\-]", "_", namespace.lower())
    return f"aurora_kv_{sanitized}"


class OpenSearchKVStorage(BaseKVStorage):
    """OpenSearch-backed key-value store.

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

    async def _ensure_index(self) -> None:
        """Create the index if it does not exist."""
        exists = await self._client.indices.exists(index=self._index)
        if not exists:
            await self._client.indices.create(
                index=self._index,
                body={
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                    "mappings": {
                        "properties": {
                            "data": {"type": "object", "enabled": True},
                        }
                    },
                },
            )

    # ── BaseKVStorage interface ──────────────────────────────────

    async def all_keys(self) -> list[str]:
        await self._ensure_index()
        keys: list[str] = []
        resp = await self._client.search(
            index=self._index,
            body={
                "query": {"match_all": {}},
                "_source": False,
                "size": 10000,
            },
        )
        for hit in resp.get("hits", {}).get("hits", []):
            keys.append(hit["_id"])
        return keys

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        await self._ensure_index()
        try:
            resp = await self._client.get(index=self._index, id=key)
            source = resp.get("_source", {})
            return source.get("data", source)
        except Exception:
            return None

    async def get_by_ids(
        self, keys: list[str]
    ) -> list[Optional[dict[str, Any]]]:
        if not keys:
            return []
        await self._ensure_index()
        resp = await self._client.mget(
            index=self._index,
            body={"ids": keys},
        )
        lookup: dict[str, dict[str, Any]] = {}
        for doc in resp.get("docs", []):
            if doc.get("found"):
                source = doc.get("_source", {})
                lookup[doc["_id"]] = source.get("data", source)
        return [lookup.get(k) for k in keys]

    async def get_by_field(
        self, field: str, value: Any
    ) -> list[dict[str, Any]]:
        await self._ensure_index()
        resp = await self._client.search(
            index=self._index,
            body={
                "query": {"term": {f"data.{field}": value}},
                "size": 10000,
            },
        )
        out: list[dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            out.append(source.get("data", source))
        return out

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        await self._ensure_index()
        body: list[dict[str, Any]] = []
        for key, record in data.items():
            body.append({"index": {"_index": self._index, "_id": key}})
            body.append({"data": record})
        await self._client.bulk(body=body, refresh="wait_for")

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        await self._ensure_index()
        body: list[dict[str, Any]] = []
        for key in keys:
            body.append({"delete": {"_index": self._index, "_id": key}})
        if body:
            await self._client.bulk(body=body, refresh="wait_for")

    async def drop(self) -> None:
        try:
            exists = await self._client.indices.exists(index=self._index)
            if exists:
                await self._client.indices.delete(index=self._index)
        except Exception as exc:
            logger.warning("Failed to drop index %s: %s", self._index, exc)
