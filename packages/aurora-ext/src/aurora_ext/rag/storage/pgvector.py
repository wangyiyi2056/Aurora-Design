"""PostgreSQL + pgvector-backed vector storage.

Production-grade vector store using ``psycopg`` (v3) async connection
pool with the pgvector extension for cosine-similarity search.
Each namespace maps to a dedicated table ``aurora_vector_{namespace}``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseVectorStorage

logger = logging.getLogger(__name__)


def _sanitize_table_name(namespace: str) -> str:
    """Convert namespace to a safe SQL table suffix."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", namespace)
    return f"aurora_vector_{sanitized}"


class PGVectorStorage(BaseVectorStorage):
    """PostgreSQL + pgvector-backed vector storage with HNSW indexing."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        self._table = _sanitize_table_name(namespace)
        self._table_ready = False

        self._embedding_func = global_config.get("embedding_func")

        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

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
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id          TEXT        PRIMARY KEY,
                    content     TEXT        NOT NULL DEFAULT '',
                    embedding   vector({self._embedding_dim}),
                    metadata    JSONB       NOT NULL DEFAULT '{{}}'::jsonb,
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self._table}_hnsw_idx
                ON {self._table}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128);
                """
            )
            await conn.commit()
        self._table_ready = True

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        await self._ensure_table()
        async with self._pool.connection() as conn:
            for key, record in data.items():
                content = record.get("content", "")
                vector = record.get("__vector__")
                meta = {
                    k: v
                    for k, v in record.items()
                    if k not in ("content", "__vector__")
                }

                if vector is not None:
                    vec_str = "[" + ",".join(str(float(x)) for x in vector) + "]"
                    await conn.execute(
                        f"""
                        INSERT INTO {self._table} (id, content, embedding, metadata, updated_at)
                        VALUES (%s, %s, %s::vector, %s, now())
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            updated_at = now()
                        """,
                        [key, content, vec_str, json.dumps(meta, ensure_ascii=False)],
                    )
                else:
                    await conn.execute(
                        f"""
                        INSERT INTO {self._table} (id, content, metadata, updated_at)
                        VALUES (%s, %s, %s, now())
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            updated_at = now()
                        """,
                        [key, content, json.dumps(meta, ensure_ascii=False)],
                    )
            await conn.commit()

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        await self._ensure_table()

        if self._embedding_func is None:
            logger.warning("No embedding function; cannot perform vector query")
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_embedding = vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])
        vec_str = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"""
                SELECT id, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM {self._table}
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [vec_str, vec_str, top_k],
            )
            rows = await cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            score = float(row[3])
            if score < cosine_threshold:
                continue
            record: dict[str, Any] = {
                "id": row[0],
                "content": row[1],
                "score": score,
            }
            metadata = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            record.update(metadata)
            out.append(record)
        return out

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(
                f"DELETE FROM {self._table} WHERE id = ANY(%s)",
                [ids],
            )
            await conn.commit()

    async def drop(self) -> None:
        await self._ensure_table()
        async with self._pool.connection() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {self._table};")
            await conn.commit()
