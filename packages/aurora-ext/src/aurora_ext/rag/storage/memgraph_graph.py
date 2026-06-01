"""Memgraph-backed graph storage.

Production-grade knowledge graph using the ``neo4j`` async Python
driver.  Memgraph is wire-compatible with Neo4j's Bolt protocol and
supports Cypher, allowing this implementation to share the query
patterns of ``Neo4jGraphStorage`` while targeting Memgraph's
default port (7688) and capabilities.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseGraphStorage

logger = logging.getLogger(__name__)

_COMPLEX_FIELDS = frozenset({"source_ids", "file_paths", "keywords"})


def _serialize_value(value: Any) -> Any:
    """Convert lists/dicts to JSON strings for property storage."""
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


class MemgraphStorage(BaseGraphStorage):
    """Memgraph-backed knowledge graph storage (Cypher-compatible)."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        self._ns_prefix = f"{namespace}__"
        self._indexes_ready = False

        uri = (
            global_config.get("memgraph_uri")
            or os.environ.get("AURORA_MEMGRAPH_URI")
            or "bolt://localhost:7688"
        )
        user = (
            global_config.get("memgraph_user")
            or os.environ.get("AURORA_MEMGRAPH_USER")
            or ""
        )
        password = (
            global_config.get("memgraph_password")
            or os.environ.get("AURORA_MEMGRAPH_PASSWORD")
            or ""
        )

        from neo4j import AsyncGraphDatabase

        auth = (user, password) if user else None
        self._driver = AsyncGraphDatabase.driver(uri, auth=auth)

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            async with self._driver.session() as session:
                await session.run(
                    "CREATE INDEX ON :Entity(id)"
                )
                await session.run(
                    "CREATE INDEX ON :Entity(namespace)"
                )
            self._indexes_ready = True
        except Exception as exc:
            logger.warning("Failed to create Memgraph indexes: %s", exc)

    def _ns_node_id(self, node_id: str) -> str:
        return f"{self._ns_prefix}{node_id}"

    def _strip_ns_prefix(self, ns_id: str) -> str:
        if ns_id.startswith(self._ns_prefix):
            return ns_id[len(self._ns_prefix):]
        return ns_id

    # ── Node operations ──────────────────────────────────────────

    async def has_node(self, node_id: str) -> bool:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:Entity {id: $id, namespace: $ns}) "
                "RETURN count(n) > 0 AS exists",
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )
            record = await result.single()
            return bool(record["exists"]) if record else False

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:Entity {id: $id, namespace: $ns}) RETURN n",
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )
            record = await result.single()
            if record is None:
                return None
            props = _deserialize_props(dict(record["n"]))
            props["id"] = node_id
            props.pop("namespace", None)
            return props

    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        await self._ensure_indexes()
        safe_data: dict[str, Any] = {}
        for k, v in node_data.items():
            safe_data[k] = _serialize_value(v)
        safe_data["id"] = self._ns_node_id(node_id)
        safe_data["namespace"] = self.namespace
        if "label" not in safe_data:
            safe_data["label"] = node_id

        async with self._driver.session() as session:
            await session.run(
                """
                MERGE (n:Entity {id: $props.id, namespace: $props.namespace})
                SET n += $props
                """,
                props=safe_data,
            )

    async def delete_node(self, node_id: str) -> None:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (n:Entity {id: $id, namespace: $ns})
                DETACH DELETE n
                """,
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )

    async def node_degree(self, node_id: str) -> int:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Entity {id: $id, namespace: $ns})
                RETURN size((n)--()) AS degree
                """,
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )
            record = await result.single()
            return int(record["degree"]) if record else 0

    async def get_all_labels(self) -> list[str]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:Entity {namespace: $ns}) RETURN n.label AS label",
                ns=self.namespace,
            )
            labels: list[str] = []
            async for record in result:
                label = record.get("label")
                if label:
                    labels.append(label)
            return labels

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Entity {namespace: $ns})
                RETURN n.label AS label, size((n)--()) AS degree
                ORDER BY degree DESC
                LIMIT $limit
                """,
                ns=self.namespace,
                limit=limit,
            )
            labels: list[str] = []
            async for record in result:
                label = record.get("label")
                if label:
                    labels.append(label)
            return labels

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (n:Entity {namespace: $ns})
                WHERE toLower(n.label) CONTAINS toLower($query)
                RETURN n.label AS label
                LIMIT $limit
                """,
                ns=self.namespace,
                query=query,
                limit=limit,
            )
            labels: list[str] = []
            async for record in result:
                label = record.get("label")
                if label:
                    labels.append(label)
            return labels

    # ── Edge operations ──────────────────────────────────────────

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {id: $src, namespace: $ns})
                      -[r:RELATED]->
                      (b:Entity {id: $tgt, namespace: $ns})
                RETURN count(r) > 0 AS exists
                """,
                src=self._ns_node_id(source_id),
                tgt=self._ns_node_id(target_id),
                ns=self.namespace,
            )
            record = await result.single()
            return bool(record["exists"]) if record else False

    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {id: $src, namespace: $ns})
                      -[r:RELATED]->
                      (b:Entity {id: $tgt, namespace: $ns})
                RETURN r
                """,
                src=self._ns_node_id(source_id),
                tgt=self._ns_node_id(target_id),
                ns=self.namespace,
            )
            record = await result.single()
            if record is None:
                return None
            props = _deserialize_props(dict(record["r"]))
            props["source_id"] = source_id
            props["target_id"] = target_id
            return props

    async def upsert_edge(
        self, source_id: str, target_id: str, edge_data: dict[str, Any]
    ) -> None:
        await self._ensure_indexes()
        safe_data: dict[str, Any] = {}
        for k, v in edge_data.items():
            safe_data[k] = _serialize_value(v)
        safe_data["namespace"] = self.namespace

        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (a:Entity {id: $src, namespace: $ns})
                MATCH (b:Entity {id: $tgt, namespace: $ns})
                MERGE (a)-[r:RELATED {namespace: $ns}]->(b)
                SET r += $props
                """,
                src=self._ns_node_id(source_id),
                tgt=self._ns_node_id(target_id),
                ns=self.namespace,
                props=safe_data,
            )

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (a:Entity {id: $src, namespace: $ns})
                      -[r:RELATED]->
                      (b:Entity {id: $tgt, namespace: $ns})
                DELETE r
                """,
                src=self._ns_node_id(source_id),
                tgt=self._ns_node_id(target_id),
                ns=self.namespace,
            )

    async def edge_degree(self, source_id: str, target_id: str) -> int:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {id: $src, namespace: $ns})
                      -[r:RELATED]->
                      (b:Entity {id: $tgt, namespace: $ns})
                RETURN COALESCE(r.weight, 1) AS weight
                """,
                src=self._ns_node_id(source_id),
                tgt=self._ns_node_id(target_id),
                ns=self.namespace,
            )
            record = await result.single()
            return int(record["weight"]) if record else 0

    # ── Traversal ────────────────────────────────────────────────

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {id: $id, namespace: $ns})
                      -[r:RELATED]-(b:Entity)
                RETURN a.id AS src, b.id AS tgt
                """,
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )
            edges: list[tuple[str, str]] = []
            async for record in result:
                src = self._strip_ns_prefix(record["src"])
                tgt = self._strip_ns_prefix(record["tgt"])
                edges.append((src, tgt))
            return edges

    async def get_neighbors(self, node_id: str) -> list[str]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {id: $id, namespace: $ns})--(b:Entity)
                RETURN DISTINCT b.id AS neighbor
                """,
                id=self._ns_node_id(node_id),
                ns=self.namespace,
            )
            neighbors: list[str] = []
            async for record in result:
                neighbors.append(self._strip_ns_prefix(record["neighbor"]))
            return neighbors

    async def get_connected_subgraph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """BFS traversal from *label* using Cypher variable-length paths."""
        await self._ensure_indexes()

        if label == "*":
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (n:Entity {namespace: $ns})
                    WITH n, size((n)--()) AS degree
                    ORDER BY degree DESC
                    LIMIT $max_nodes
                    WITH collect(n) AS nodes
                    UNWIND nodes AS n
                    OPTIONAL MATCH (n)-[r:RELATED]-(m:Entity {namespace: $ns})
                    WHERE m IN nodes
                    RETURN nodes, collect(DISTINCT r) AS rels
                    """,
                    ns=self.namespace,
                    max_nodes=max_nodes,
                )
                record = await result.single()
                if record is None:
                    return {"nodes": [], "edges": []}
                return self._unpack_subgraph_record(record)

        ns_id = self._ns_node_id(label)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH path = (start:Entity {id: $id, namespace: $ns})
                      -[*1..$depth]-
                      (connected:Entity {namespace: $ns})
                WITH connected, relationships(path) AS rels
                LIMIT $max_nodes
                WITH collect(DISTINCT connected) AS nodes,
                     collect(DISTINCT rels) AS all_rels
                UNWIND all_rels AS rel_list
                UNWIND rel_list AS r
                RETURN nodes, collect(DISTINCT r) AS edges
                """,
                id=ns_id,
                ns=self.namespace,
                depth=max_depth,
                max_nodes=max_nodes,
            )
            record = await result.single()

            if record is None or not record.get("nodes"):
                node_result = await session.run(
                    "MATCH (n:Entity {id: $id, namespace: $ns}) RETURN n",
                    id=ns_id,
                    ns=self.namespace,
                )
                single = await node_result.single()
                if single is None:
                    return {"nodes": [], "edges": []}
                props = _deserialize_props(dict(single["n"]))
                props["id"] = label
                props.pop("namespace", None)
                return {"nodes": [props], "edges": []}

            result_data = self._unpack_subgraph_record(record)

            seen = {n["id"] for n in result_data["nodes"]}
            if label not in seen:
                start_result = await session.run(
                    "MATCH (n:Entity {id: $id, namespace: $ns}) RETURN n",
                    id=ns_id,
                    ns=self.namespace,
                )
                start_rec = await start_result.single()
                if start_rec:
                    props = _deserialize_props(dict(start_rec["n"]))
                    props["id"] = label
                    props.pop("namespace", None)
                    result_data["nodes"].insert(0, props)

            return result_data

    def _unpack_subgraph_record(self, record: Any) -> dict[str, Any]:
        """Unpack a Memgraph result record into nodes/edges dicts."""
        nodes_out: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for node in record.get("nodes", []):
            props = _deserialize_props(dict(node))
            raw_id = props.pop("id", "")
            clean_id = self._strip_ns_prefix(raw_id)
            if clean_id not in seen_ids:
                seen_ids.add(clean_id)
                props["id"] = clean_id
                props.pop("namespace", None)
                nodes_out.append(props)

        rels_key = "rels" if "rels" in record.keys() else "edges"
        edges_out: list[dict[str, Any]] = []
        for rel in record.get(rels_key, []):
            rprops = _deserialize_props(dict(rel))
            rprops.pop("namespace", None)
            try:
                start_id = self._strip_ns_prefix(str(rel.start_node["id"]))
                end_id = self._strip_ns_prefix(str(rel.end_node["id"]))
                rprops["source_id"] = start_id
                rprops["target_id"] = end_id
            except (AttributeError, KeyError):
                pass
            edges_out.append(rprops)

        return {"nodes": nodes_out, "edges": edges_out}

    # ── Bulk ─────────────────────────────────────────────────────

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n:Entity {namespace: $ns}) RETURN n",
                ns=self.namespace,
            )
            out: list[dict[str, Any]] = []
            async for record in result:
                props = _deserialize_props(dict(record["n"]))
                raw_id = props.pop("id", "")
                props["id"] = self._strip_ns_prefix(raw_id)
                props.pop("namespace", None)
                out.append(props)
            return out

    async def get_all_edges(self) -> list[dict[str, Any]]:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {namespace: $ns})
                      -[r:RELATED]->
                      (b:Entity {namespace: $ns})
                RETURN a.id AS src, b.id AS tgt, r
                """,
                ns=self.namespace,
            )
            out: list[dict[str, Any]] = []
            async for record in result:
                rprops = _deserialize_props(dict(record["r"]))
                rprops.pop("namespace", None)
                rprops["source_id"] = self._strip_ns_prefix(record["src"])
                rprops["target_id"] = self._strip_ns_prefix(record["tgt"])
                out.append(rprops)
            return out

    async def drop(self) -> None:
        await self._ensure_indexes()
        async with self._driver.session() as session:
            await session.run(
                "MATCH (n:Entity {namespace: $ns}) DETACH DELETE n",
                ns=self.namespace,
            )
