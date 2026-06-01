"""PostgreSQL-backed key-value storage.

Production-grade KV store using ``psycopg`` (v3) async connection pool.
Each namespace maps to rows in a shared ``aurora_kv`` table, partitioned
by the ``namespace`` column.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseKVStorage

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aurora_kv (
    namespace   TEXT        NOT NULL,
    key         TEXT        NOT NULL,
    value       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, key)
);
"""


class PostgresKVStorage(BaseKVStorage):
    """PostgreSQL JSONB-backed key-value store."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        self._table_ready = False

        uri = (
            global_config.get("postgres_uri")
            or os.environ.get("AURORA_POSTGRES_URI")
            or ""
        )
        if not uri:
            raise ValueError(
                "postgres_uri must be set in global_config or AURORA_POSTGRES_URI env var"
            )

        from psycopg_pool import AsyncConnectionPool

        self._pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=2,
            max_size=10,
            timeout=30,
            open=False,
        )

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await self._pool.open()
        async with self._pool.connection() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_aurora_kv_namespace "
                "ON aurora_kv (namespace);"
            )
            await conn.commit()
        self._table_ready = True

    # ── BaseKVStorage interface ──────────────────────────────────

    async def all_keys(self) -> list[str]:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT key FROM aurora_kv WHERE namespace = %s",
                [self.namespace],
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT value FROM aurora_kv WHERE namespace = %s AND key = %s",
                [self.namespace, key],
            )
            row = await cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    async def get_by_ids(
        self, keys: list[str]
    ) -> list[Optional[dict[str, Any]]]:
        if not keys:
            return []
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT key, value FROM aurora_kv "
                "WHERE namespace = %s AND key = ANY(%s)",
                [self.namespace, keys],
            )
            rows = await cur.fetchall()
            lookup: dict[str, dict[str, Any]] = {}
            for row in rows:
                val = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                lookup[row[0]] = val
            return [lookup.get(k) for k in keys]

    async def get_by_field(
        self, field: str, value: Any
    ) -> list[dict[str, Any]]:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT value FROM aurora_kv "
                "WHERE namespace = %s AND value->>%s = %s",
                [self.namespace, field, str(value)],
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                val = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                out.append(val)
            return out

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        await self._ensure_table()
        async with self._pool.connection() as conn:
            for key, record in data.items():
                await conn.execute(
                    """
                    INSERT INTO aurora_kv (namespace, key, value, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (namespace, key) DO UPDATE
                        SET value = EXCLUDED.value,
                            updated_at = now()
                    """,
                    [self.namespace, key, json.dumps(record, ensure_ascii=False)],
                )
            await conn.commit()

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_kv "
                "WHERE namespace = %s AND key = ANY(%s)",
                [self.namespace, keys],
            )
            await conn.commit()

    async def drop(self) -> None:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_kv WHERE namespace = %s",
                [self.namespace],
            )
            await conn.commit()
