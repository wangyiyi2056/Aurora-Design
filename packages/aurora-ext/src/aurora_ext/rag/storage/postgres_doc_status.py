"""PostgreSQL-backed document status storage.

Production-grade document status tracker using ``psycopg`` (v3) async
connection pool.  Replaces the JSON-file backend for multi-process and
multi-node deployments.
"""

from __future__ import annotations

import json
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

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS aurora_doc_status (
    namespace       TEXT        NOT NULL,
    doc_id          TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'PENDING',
    file_path       TEXT        NOT NULL DEFAULT '',
    content_summary TEXT        NOT NULL DEFAULT '',
    content_length  INT         NOT NULL DEFAULT 0,
    chunks_count    INT         NOT NULL DEFAULT 0,
    error_msg       TEXT,
    track_id        TEXT        NOT NULL DEFAULT '',
    kb_name         TEXT        NOT NULL DEFAULT '',
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    content_hash    TEXT        NOT NULL DEFAULT '',
    duplicate_kind  TEXT        NOT NULL DEFAULT '',
    basename        TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, doc_id)
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_doc_status_ns_kb_status "
    "ON aurora_doc_status (namespace, kb_name, status);",
    "CREATE INDEX IF NOT EXISTS idx_doc_status_ns_track "
    "ON aurora_doc_status (namespace, track_id);",
    "CREATE INDEX IF NOT EXISTS idx_doc_status_ns_kb_hash "
    "ON aurora_doc_status (namespace, kb_name, content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_doc_status_ns_kb_basename "
    "ON aurora_doc_status (namespace, kb_name, basename);",
]

_DOC_COLS = (
    "doc_id", "status", "file_path", "content_summary",
    "content_length", "chunks_count", "error_msg", "track_id",
    "kb_name", "metadata", "created_at", "updated_at",
)


class PostgresDocStatusStorage(BaseDocStatusStorage):
    """PostgreSQL-backed document status storage."""

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
                "postgres_uri must be set in global_config or "
                "AURORA_POSTGRES_URI env var"
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
            for idx_sql in _CREATE_INDEXES_SQL:
                await conn.execute(idx_sql)
            await conn.commit()
        self._table_ready = True

    @staticmethod
    def _to_info(row: dict[str, Any]) -> DocStatusInfo:
        """Convert a database row to a :class:`DocStatusInfo`."""
        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return DocStatusInfo(
            id=row.get("doc_id", ""),
            file_path=row.get("file_path", ""),
            status=DocStatus(row.get("status", "PENDING")),
            content_summary=row.get("content_summary", ""),
            content_length=row.get("content_length", 0),
            chunks_count=row.get("chunks_count", 0),
            error_msg=row.get("error_msg"),
            track_id=row.get("track_id", ""),
            metadata=metadata,
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            kb_name=row.get("kb_name", ""),
        )

    @staticmethod
    def _row_to_dict(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
        """Convert a psycopg row tuple to a plain dict."""
        return dict(zip(columns, row))

    # ── BaseDocStatusStorage interface ───────────────────────────

    async def get_status(self, doc_id: str) -> Optional[DocStatusInfo]:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                "WHERE namespace = %s AND doc_id = %s",
                [self.namespace, doc_id],
            )
            row = await cur.fetchone()
            if row is None:
                return None
            return self._to_info(self._row_to_dict(row, _DOC_COLS))

    async def get_statuses_by_ids(
        self, doc_ids: list[str]
    ) -> list[Optional[DocStatusInfo]]:
        if not doc_ids:
            return []
        await self._ensure_table()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                "WHERE namespace = %s AND doc_id = ANY(%s)",
                [self.namespace, doc_ids],
            )
            rows = await cur.fetchall()
            lookup: dict[str, DocStatusInfo] = {}
            for row in rows:
                info = self._to_info(self._row_to_dict(row, _DOC_COLS))
                lookup[info.id] = info
            return [lookup.get(did) for did in doc_ids]

    async def get_docs_by_status(
        self, status: DocStatus, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        await self._ensure_table()
        params: list[Any] = [self.namespace, status.value]
        kb_clause = ""
        if kb_name:
            kb_clause = " AND kb_name = %s"
            params.append(kb_name)

        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                f"WHERE namespace = %s AND status = %s{kb_clause}",
                params,
            )
            rows = await cur.fetchall()
            return [
                self._to_info(self._row_to_dict(row, _DOC_COLS))
                for row in rows
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
        await self._ensure_table()

        # Whitelist sort field to prevent SQL injection
        allowed_sort = {
            "created_at", "updated_at", "status", "file_path",
            "content_length", "chunks_count", "kb_name",
        }
        if sort_field not in allowed_sort:
            sort_field = "created_at"
        order_dir = "DESC" if sort_direction == "desc" else "ASC"

        where_parts = ["namespace = %s"]
        params: list[Any] = [self.namespace]

        if kb_name:
            where_parts.append("kb_name = %s")
            params.append(kb_name)
        if status_filters:
            placeholders = ", ".join(["%s"] * len(status_filters))
            where_parts.append(f"status IN ({placeholders})")
            params.extend(s.value for s in status_filters)

        where_clause = " AND ".join(where_parts)
        offset = (page - 1) * page_size

        async with self._pool.connection() as conn:
            # Count query
            cur = await conn.execute(
                f"SELECT COUNT(*) FROM aurora_doc_status "
                f"WHERE {where_clause}",
                params,
            )
            count_row = await cur.fetchone()
            total = count_row[0] if count_row else 0

            # Data query
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                f"WHERE {where_clause} "
                f"ORDER BY {sort_field} {order_dir} "
                f"LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            rows = await cur.fetchall()
            docs = [
                self._to_info(self._row_to_dict(row, _DOC_COLS))
                for row in rows
            ]

        return docs, total

    async def get_status_counts(
        self, *, kb_name: str | None = None
    ) -> dict[str, int]:
        await self._ensure_table()
        params: list[Any] = [self.namespace]
        kb_clause = ""
        if kb_name:
            kb_clause = " AND kb_name = %s"
            params.append(kb_name)

        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT status, COUNT(*) FROM aurora_doc_status "
                f"WHERE namespace = %s{kb_clause} "
                "GROUP BY status",
                params,
            )
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}

    async def upsert(self, docs: dict[str, DocStatusInfo]) -> None:
        if not docs:
            return
        await self._ensure_table()
        now = _now_iso()
        async with self._pool.connection() as conn:
            for doc_id, info in docs.items():
                record = asdict(info)
                record["status"] = info.status.value
                metadata_json = json.dumps(
                    record.get("metadata", {}), ensure_ascii=False
                )

                await conn.execute(
                    """
                    INSERT INTO aurora_doc_status
                        (namespace, doc_id, status, file_path,
                         content_summary, content_length, chunks_count,
                         error_msg, track_id, kb_name, metadata,
                         created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                    ON CONFLICT (namespace, doc_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        file_path = EXCLUDED.file_path,
                        content_summary = EXCLUDED.content_summary,
                        content_length = EXCLUDED.content_length,
                        chunks_count = EXCLUDED.chunks_count,
                        error_msg = EXCLUDED.error_msg,
                        track_id = EXCLUDED.track_id,
                        kb_name = EXCLUDED.kb_name,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    [
                        self.namespace,
                        doc_id,
                        record["status"],
                        record.get("file_path", ""),
                        record.get("content_summary", ""),
                        record.get("content_length", 0),
                        record.get("chunks_count", 0),
                        record.get("error_msg"),
                        record.get("track_id", ""),
                        record.get("kb_name", ""),
                        metadata_json,
                        record.get("created_at", now),
                    ],
                )
            await conn.commit()

    async def update_status(
        self,
        doc_id: str,
        status: DocStatus,
        error_msg: Optional[str] = None,
        **extra: Any,
    ) -> None:
        await self._ensure_table()
        set_parts = ["status = %s", "updated_at = now()"]
        params: list[Any] = [status.value]

        if error_msg is not None:
            set_parts.append("error_msg = %s")
            params.append(error_msg)

        for k, v in extra.items():
            set_parts.append(f"{k} = %s")
            params.append(v)

        set_clause = ", ".join(set_parts)
        insert_params: list[Any] = [self.namespace, doc_id, status.value]

        async with self._pool.connection() as conn:
            await conn.execute(
                f"""
                INSERT INTO aurora_doc_status
                    (namespace, doc_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, now(), now())
                ON CONFLICT (namespace, doc_id) DO UPDATE
                    SET {set_clause}
                """,
                insert_params + params,
            )
            await conn.commit()

    async def delete(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_doc_status "
                "WHERE namespace = %s AND doc_id = ANY(%s)",
                [self.namespace, doc_ids],
            )
            await conn.commit()

    async def drop(self) -> None:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_doc_status WHERE namespace = %s",
                [self.namespace],
            )
            await conn.commit()

    # ── Extra convenience methods ────────────────────────────────

    async def get_doc_by_basename(
        self, basename: str, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        """Find documents by their file basename."""
        await self._ensure_table()
        params: list[Any] = [self.namespace, basename]
        kb_clause = ""
        if kb_name:
            kb_clause = " AND kb_name = %s"
            params.append(kb_name)

        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                f"WHERE namespace = %s AND basename = %s{kb_clause}",
                params,
            )
            rows = await cur.fetchall()
            return [
                self._to_info(self._row_to_dict(row, _DOC_COLS))
                for row in rows
            ]

    async def get_doc_by_content_hash(
        self, content_hash: str, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        """Find documents by content hash (duplicate detection)."""
        await self._ensure_table()
        params: list[Any] = [self.namespace, content_hash]
        kb_clause = ""
        if kb_name:
            kb_clause = " AND kb_name = %s"
            params.append(kb_name)

        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {', '.join(_DOC_COLS)} FROM aurora_doc_status "
                f"WHERE namespace = %s AND content_hash = %s{kb_clause}",
                params,
            )
            rows = await cur.fetchall()
            return [
                self._to_info(self._row_to_dict(row, _DOC_COLS))
                for row in rows
            ]
