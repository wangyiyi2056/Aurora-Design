"""Redis-backed key-value storage.

Production-grade KV store using ``redis.asyncio`` (aioredis).
Each namespace maps to a Redis hash with key prefix
``aurora_kv:{namespace}:``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseKVStorage

logger = logging.getLogger(__name__)


class RedisKVStorage(BaseKVStorage):
    """Redis-backed key-value store with hash-based namespacing."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        self._prefix = f"aurora_kv:{namespace}:"

        uri = (
            global_config.get("redis_uri")
            or os.environ.get("AURORA_REDIS_URI")
            or "redis://localhost:6379"
        )

        import redis.asyncio as aioredis

        self._client: aioredis.Redis = aioredis.from_url(
            uri, decode_responses=True
        )

    def _key(self, key: str) -> str:
        """Build the full Redis key with namespace prefix."""
        return f"{self._prefix}{key}"

    def _strip_prefix(self, redis_key: str) -> str:
        """Remove the namespace prefix from a Redis key."""
        if redis_key.startswith(self._prefix):
            return redis_key[len(self._prefix):]
        return redis_key

    # ── BaseKVStorage interface ──────────────────────────────────

    async def all_keys(self) -> list[str]:
        keys: list[str] = []
        cursor = 0
        while True:
            cursor, batch = await self._client.scan(
                cursor=cursor, match=f"{self._prefix}*", count=200
            )
            keys.extend(self._strip_prefix(k) for k in batch)
            if cursor == 0:
                break
        return keys

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def get_by_ids(
        self, keys: list[str]
    ) -> list[Optional[dict[str, Any]]]:
        if not keys:
            return []
        pipeline = self._client.pipeline()
        for key in keys:
            pipeline.get(self._key(key))
        results = await pipeline.execute()
        out: list[Optional[dict[str, Any]]] = []
        for raw in results:
            if raw is None:
                out.append(None)
            else:
                out.append(json.loads(raw))
        return out

    async def get_by_field(
        self, field: str, value: Any
    ) -> list[dict[str, Any]]:
        all_keys = await self.all_keys()
        if not all_keys:
            return []

        pipeline = self._client.pipeline()
        for key in all_keys:
            pipeline.get(self._key(key))
        results = await pipeline.execute()

        out: list[dict[str, Any]] = []
        for raw in results:
            if raw is None:
                continue
            record = json.loads(raw)
            if record.get(field) == value:
                out.append(record)
        return out

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        pipeline = self._client.pipeline()
        for key, record in data.items():
            pipeline.set(
                self._key(key),
                json.dumps(record, ensure_ascii=False),
            )
        await pipeline.execute()

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        pipeline = self._client.pipeline()
        for key in keys:
            pipeline.delete(self._key(key))
        await pipeline.execute()

    async def drop(self) -> None:
        all_keys = await self.all_keys()
        if not all_keys:
            return
        pipeline = self._client.pipeline()
        for key in all_keys:
            pipeline.delete(self._key(key))
        await pipeline.execute()
