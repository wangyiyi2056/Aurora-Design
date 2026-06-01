"""PostgreSQL-backed graph storage.

Production-grade knowledge graph using ``psycopg`` (v3) async
connection pool.  Nodes and edges are stored in two tables
(``aurora_graph_nodes`` and ``aurora_graph_edges``) partitioned
by namespace.

This implementation does NOT require the Apache AGE extension —
it uses plain relational tables with JSONB for properties, making
it deployable on any PostgreSQL 12+ instance.
"""

from __future__ import annotations

import json
import logging
import os
from collections import deque
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseGraphStorage

logger = logging.getLogger(__name__)

_COMPLEX_FIELDS = frozenset({"source_ids", "file_paths", "keywords"})


def _serialize_value(value: Any) -> Any:
    """Convert lists/dicts to JSON strings for storage."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _deserialize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON-encoded string properties back to Python objects."""
    out: dict[str, Any] = {}
    for k, v in props.items():
        if isinstance(v, str) and k in _COMPLEX_FIELDS:
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[k] = v
        else:
            out[k] = v
    return out


_CREATE_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS aurora_graph_nodes (
    namespace   TEXT        NOT NULL,
    node_id     TEXT        NOT NULL,
    label       TEXT        NOT NULL DEFAULT '',
    properties  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, node_id)
);
"""

_CREATE_EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS aurora_graph_edges (
    namespace   TEXT        NOT NULL,
    source_id   TEXT        NOT NULL,
    target_id   TEXT        NOT NULL,
    properties  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, source_id, target_id)
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_graph_nodes_ns_label "
    "ON aurora_graph_nodes (namespace, label);",
    "CREATE INDEX IF NOT EXISTS idx_graph_edges_ns_src "
    "ON aurora_graph_edges (namespace, source_id);",
    "CREATE INDEX IF NOT EXISTS idx_graph_edges_ns_tgt "
    "ON aurora_graph_edges (namespace, target_id);",
]


class PGGraphStorage(BaseGraphStorage):
    """PostgreSQL-backed graph storage using relational tables."""

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

    async def _ensure_tables(self) -> None:
        if self._table_ready:
            return
        await self._pool.open()
        async with self._pool.connection() as conn:
            await conn.execute(_CREATE_NODES_TABLE)
            await conn.execute(_CREATE_EDGES_TABLE)
            for idx_sql in _CREATE_INDEXES:
                await conn.execute(idx_sql)
            await conn.commit()
        self._table_ready = True

    # ── Node operations ──────────────────────────────────────────

    async def has_node(self, node_id: str) -> bool:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM aurora_graph_nodes "
                "WHERE namespace = %s AND node_id = %s",
                [self.namespace, node_id],
            )
            return await cur.fetchone() is not None

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT node_id, label, properties FROM aurora_graph_nodes "
                "WHERE namespace = %s AND node_id = %s",
                [self.namespace, node_id],
            )
            row = await cur.fetchone()
            if row is None:
                return None
            props = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            props = _deserialize_props(props)
            props["id"] = row[0]
            props["label"] = row[1]
            return props

    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        await self._ensure_tables()
        safe_data: dict[str, Any] = {}
        for k, v in node_data.items():
            safe_data[k] = _serialize_value(v)

        label = safe_data.pop("label", node_id)

        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO aurora_graph_nodes (namespace, node_id, label, properties, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (namespace, node_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    properties = EXCLUDED.properties,
                    updated_at = now()
                """,
                [self.namespace, node_id, label, json.dumps(safe_data, ensure_ascii=False)],
            )
            await conn.commit()

    async def delete_node(self, node_id: str) -> None:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_graph_edges "
                "WHERE namespace = %s AND (source_id = %s OR target_id = %s)",
                [self.namespace, node_id, node_id],
            )
            await conn.execute(
                "DELETE FROM aurora_graph_nodes "
                "WHERE namespace = %s AND node_id = %s",
                [self.namespace, node_id],
            )
            await conn.commit()

    async def node_degree(self, node_id: str) -> int:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) FROM aurora_graph_edges "
                "WHERE namespace = %s AND (source_id = %s OR target_id = %s)",
                [self.namespace, node_id, node_id],
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def get_all_labels(self) -> list[str]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT label FROM aurora_graph_nodes WHERE namespace = %s",
                [self.namespace],
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT n.label, COUNT(e.source_id) + COUNT(e2.source_id) AS degree
                FROM aurora_graph_nodes n
                LEFT JOIN aurora_graph_edges e
                    ON n.namespace = e.namespace AND n.node_id = e.source_id
                LEFT JOIN aurora_graph_edges e2
                    ON n.namespace = e2.namespace AND n.node_id = e2.target_id
                WHERE n.namespace = %s
                GROUP BY n.node_id, n.label
                ORDER BY degree DESC
                LIMIT %s
                """,
                [self.namespace, limit],
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT label FROM aurora_graph_nodes "
                "WHERE namespace = %s AND label ILIKE %s "
                "LIMIT %s",
                [self.namespace, f"%{query}%", limit],
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    # ── Edge operations ──────────────────────────────────────────

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM aurora_graph_edges "
                "WHERE namespace = %s AND source_id = %s AND target_id = %s",
                [self.namespace, source_id, target_id],
            )
            return await cur.fetchone() is not None

    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT properties FROM aurora_graph_edges "
                "WHERE namespace = %s AND source_id = %s AND target_id = %s",
                [self.namespace, source_id, target_id],
            )
            row = await cur.fetchone()
            if row is None:
                return None
            props = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            props = _deserialize_props(props)
            props["source_id"] = source_id
            props["target_id"] = target_id
            return props

    async def upsert_edge(
        self, source_id: str, target_id: str, edge_data: dict[str, Any]
    ) -> None:
        await self._ensure_tables()
        safe_data: dict[str, Any] = {}
        for k, v in edge_data.items():
            safe_data[k] = _serialize_value(v)

        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO aurora_graph_edges
                    (namespace, source_id, target_id, properties, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (namespace, source_id, target_id) DO UPDATE SET
                    properties = EXCLUDED.properties,
                    updated_at = now()
                """,
                [
                    self.namespace,
                    source_id,
                    target_id,
                    json.dumps(safe_data, ensure_ascii=False),
                ],
            )
            await conn.commit()

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_graph_edges "
                "WHERE namespace = %s AND source_id = %s AND target_id = %s",
                [self.namespace, source_id, target_id],
            )
            await conn.commit()

    async def edge_degree(self, source_id: str, target_id: str) -> int:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT properties FROM aurora_graph_edges "
                "WHERE namespace = %s AND source_id = %s AND target_id = %s",
                [self.namespace, source_id, target_id],
            )
            row = await cur.fetchone()
            if row is None:
                return 0
            props = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return int(props.get("weight", 1))

    # ── Traversal ────────────────────────────────────────────────

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT source_id, target_id FROM aurora_graph_edges "
                "WHERE namespace = %s AND (source_id = %s OR target_id = %s)",
                [self.namespace, node_id, node_id],
            )
            rows = await cur.fetchall()
            return [(row[0], row[1]) for row in rows]

    async def get_neighbors(self, node_id: str) -> list[str]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT DISTINCT
                    CASE WHEN source_id = %s THEN target_id ELSE source_id END
                FROM aurora_graph_edges
                WHERE namespace = %s AND (source_id = %s OR target_id = %s)
                """,
                [node_id, self.namespace, node_id, node_id],
            )
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def get_connected_subgraph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """BFS traversal from *label* up to *max_depth* and *max_nodes*."""
        await self._ensure_tables()

        # Handle wildcard: return top nodes by degree
        if label == "*":
            async with self._pool.connection() as conn:
                cur = await conn.execute(
                    """
                    SELECT n.node_id, n.label, n.properties
                    FROM aurora_graph_nodes n
                    WHERE n.namespace = %s
                    ORDER BY n.node_id
                    LIMIT %s
                    """,
                    [self.namespace, max_nodes],
                )
                rows = await cur.fetchall()

            if not rows:
                return {"nodes": [], "edges": []}

            node_ids = [row[0] for row in rows]
            nodes_out = self._rows_to_nodes(rows)

            edges_out = await self._get_edges_for_nodes(node_ids)
            return {"nodes": nodes_out, "edges": edges_out}

        # Check if start node exists
        start_node = await self.get_node(label)
        if start_node is None:
            return {"nodes": [], "edges": []}

        # BFS
        visited_nodes: dict[str, dict[str, Any]] = {label: start_node}
        visited_edges: list[dict[str, Any]] = []
        queue: deque[tuple[str, int]] = deque([(label, 0)])

        while queue and len(visited_nodes) < max_nodes:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            edges = await self.get_node_edges(current)
            for src, tgt in edges:
                neighbor = tgt if src == current else src
                edge_data = await self.get_edge(src, tgt)

                if edge_data and (src, tgt) not in {
                    (e["source_id"], e["target_id"]) for e in visited_edges
                }:
                    visited_edges.append(edge_data)

                if neighbor not in visited_nodes:
                    n_data = await self.get_node(neighbor)
                    if n_data:
                        visited_nodes[neighbor] = n_data
                        queue.append((neighbor, depth + 1))

        nodes_out = list(visited_nodes.values())
        return {"nodes": nodes_out, "edges": visited_edges}

    def _rows_to_nodes(self, rows: list[tuple]) -> list[dict[str, Any]]:
        """Convert DB rows to node dicts."""
        out: list[dict[str, Any]] = []
        for row in rows:
            props = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            props = _deserialize_props(props)
            props["id"] = row[0]
            props["label"] = row[1]
            out.append(props)
        return out

    async def _get_edges_for_nodes(
        self, node_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch all edges between the given node IDs."""
        if not node_ids:
            return []
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT source_id, target_id, properties "
                "FROM aurora_graph_edges "
                "WHERE namespace = %s AND source_id = ANY(%s) AND target_id = ANY(%s)",
                [self.namespace, node_ids, node_ids],
            )
            rows = await cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            props = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            props = _deserialize_props(props)
            props["source_id"] = row[0]
            props["target_id"] = row[1]
            out.append(props)
        return out

    # ── Bulk ─────────────────────────────────────────────────────

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT node_id, label, properties FROM aurora_graph_nodes "
                "WHERE namespace = %s",
                [self.namespace],
            )
            rows = await cur.fetchall()
            return self._rows_to_nodes(rows)

    async def get_all_edges(self) -> list[dict[str, Any]]:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT source_id, target_id, properties FROM aurora_graph_edges "
                "WHERE namespace = %s",
                [self.namespace],
            )
            rows = await cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            props = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            props = _deserialize_props(props)
            props["source_id"] = row[0]
            props["target_id"] = row[1]
            out.append(props)
        return out

    async def drop(self) -> None:
        await self._ensure_tables()
        async with self._pool.connection() as conn:
            await conn.execute(
                "DELETE FROM aurora_graph_edges WHERE namespace = %s",
                [self.namespace],
            )
            await conn.execute(
                "DELETE FROM aurora_graph_nodes WHERE namespace = %s",
                [self.namespace],
            )
            await conn.commit()
