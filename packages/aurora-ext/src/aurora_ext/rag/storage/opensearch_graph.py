"""OpenSearch-backed graph storage.

Knowledge graph implementation using ``opensearch-py[async]``.
Nodes and edges are stored in two separate indices:
``aurora_graph_nodes_{namespace}`` and ``aurora_graph_edges_{namespace}``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import deque
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseGraphStorage

logger = logging.getLogger(__name__)

_COMPLEX_FIELDS = frozenset({"source_ids", "file_paths", "keywords"})


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _deserialize_props(props: dict[str, Any]) -> dict[str, Any]:
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


def _sanitize_index_name(prefix: str, namespace: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_\\-]", "_", namespace.lower())
    return f"{prefix}_{sanitized}"


class OpenSearchGraphStorage(BaseGraphStorage):
    """OpenSearch-backed graph storage using dual indices."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        self._nodes_index = _sanitize_index_name("aurora_graph_nodes", namespace)
        self._edges_index = _sanitize_index_name("aurora_graph_edges", namespace)

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
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return

        for index_name, mapping in [
            (self._nodes_index, {
                "properties": {
                    "label": {"type": "keyword"},
                    "properties": {"type": "object", "enabled": True},
                }
            }),
            (self._edges_index, {
                "properties": {
                    "source_id": {"type": "keyword"},
                    "target_id": {"type": "keyword"},
                    "properties": {"type": "object", "enabled": True},
                }
            }),
        ]:
            exists = await self._client.indices.exists(index=index_name)
            if not exists:
                await self._client.indices.create(
                    index=index_name,
                    body={"mappings": mapping},
                )

        self._indexes_ready = True

    # ── Node operations ──────────────────────────────────────────

    async def has_node(self, node_id: str) -> bool:
        await self._ensure_indexes()
        try:
            await self._client.get(index=self._nodes_index, id=node_id)
            return True
        except Exception:
            return False

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        await self._ensure_indexes()
        try:
            resp = await self._client.get(index=self._nodes_index, id=node_id)
            source = resp.get("_source", {})
            props = source.get("properties", {})
            props = _deserialize_props(props)
            props["id"] = node_id
            props["label"] = source.get("label", node_id)
            return props
        except Exception:
            return None

    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        await self._ensure_indexes()
        safe_data: dict[str, Any] = {}
        for k, v in node_data.items():
            safe_data[k] = _serialize_value(v)

        label = safe_data.pop("label", node_id)
        doc = {"label": label, "properties": safe_data}

        await self._client.index(
            index=self._nodes_index, id=node_id, body=doc, refresh="wait_for"
        )

    async def delete_node(self, node_id: str) -> None:
        await self._ensure_indexes()
        # Delete all edges connected to this node
        await self._client.delete_by_query(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"source_id": node_id}},
                            {"term": {"target_id": node_id}},
                        ]
                    }
                }
            },
            refresh="wait_for",
        )
        # Delete the node
        try:
            await self._client.delete(
                index=self._nodes_index, id=node_id, refresh="wait_for"
            )
        except Exception:
            pass

    async def node_degree(self, node_id: str) -> int:
        await self._ensure_indexes()
        resp = await self._client.count(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"source_id": node_id}},
                            {"term": {"target_id": node_id}},
                        ]
                    }
                }
            },
        )
        return resp.get("count", 0)

    async def get_all_labels(self) -> list[str]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._nodes_index,
            body={
                "size": 0,
                "aggs": {
                    "labels": {
                        "terms": {"field": "label", "size": 100000}
                    }
                },
            },
        )
        buckets = resp.get("aggregations", {}).get("labels", {}).get("buckets", [])
        return [b["key"] for b in buckets]

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        await self._ensure_indexes()
        # Fetch all nodes with degree info
        resp = await self._client.search(
            index=self._nodes_index,
            body={
                "size": limit,
                "_source": ["label"],
                "sort": [{"_score": "desc"}],
                "query": {"match_all": {}},
            },
        )
        labels: list[str] = []
        for hit in resp.get("hits", {}).get("hits", []):
            label = hit.get("_source", {}).get("label", "")
            if label:
                labels.append(label)
        return labels

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._nodes_index,
            body={
                "query": {
                    "match": {
                        "label": {
                            "query": query,
                            "fuzziness": "AUTO",
                        }
                    }
                },
                "size": limit,
                "_source": ["label"],
            },
        )
        labels: list[str] = []
        for hit in resp.get("hits", {}).get("hits", []):
            label = hit.get("_source", {}).get("label", "")
            if label:
                labels.append(label)
        return labels

    # ── Edge operations ──────────────────────────────────────────

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        await self._ensure_indexes()
        resp = await self._client.count(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"source_id": source_id}},
                            {"term": {"target_id": target_id}},
                        ]
                    }
                }
            },
        )
        return resp.get("count", 0) > 0

    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"source_id": source_id}},
                            {"term": {"target_id": target_id}},
                        ]
                    }
                },
                "size": 1,
            },
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return None
        source = hits[0].get("_source", {})
        props = source.get("properties", {})
        props = _deserialize_props(props)
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

        edge_id = f"{source_id}__{target_id}"
        doc = {
            "source_id": source_id,
            "target_id": target_id,
            "properties": safe_data,
        }
        await self._client.index(
            index=self._edges_index, id=edge_id, body=doc, refresh="wait_for"
        )

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        await self._ensure_indexes()
        edge_id = f"{source_id}__{target_id}"
        try:
            await self._client.delete(
                index=self._edges_index, id=edge_id, refresh="wait_for"
            )
        except Exception:
            pass

    async def edge_degree(self, source_id: str, target_id: str) -> int:
        edge = await self.get_edge(source_id, target_id)
        if edge is None:
            return 0
        return int(edge.get("weight", 1))

    # ── Traversal ────────────────────────────────────────────────

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"source_id": node_id}},
                            {"term": {"target_id": node_id}},
                        ]
                    }
                },
                "size": 10000,
                "_source": ["source_id", "target_id"],
            },
        )
        edges: list[tuple[str, str]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            edges.append((source["source_id"], source["target_id"]))
        return edges

    async def get_neighbors(self, node_id: str) -> list[str]:
        edges = await self.get_node_edges(node_id)
        neighbors: set[str] = set()
        for src, tgt in edges:
            if src == node_id:
                neighbors.add(tgt)
            else:
                neighbors.add(src)
        return list(neighbors)

    async def get_connected_subgraph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """BFS traversal from *label*."""
        await self._ensure_indexes()

        if label == "*":
            resp = await self._client.search(
                index=self._nodes_index,
                body={"size": max_nodes, "query": {"match_all": {}}},
            )
            nodes_out: list[dict[str, Any]] = []
            node_ids: list[str] = []
            for hit in resp.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                props = _deserialize_props(source.get("properties", {}))
                props["id"] = hit["_id"]
                props["label"] = source.get("label", hit["_id"])
                nodes_out.append(props)
                node_ids.append(hit["_id"])

            if not node_ids:
                return {"nodes": [], "edges": []}

            edges_out = await self._fetch_edges_for_nodes(node_ids)
            return {"nodes": nodes_out, "edges": edges_out}

        # BFS from specific label
        start_node = await self.get_node(label)
        if start_node is None:
            return {"nodes": [], "edges": []}

        visited_nodes: dict[str, dict[str, Any]] = {label: start_node}
        visited_edges: list[dict[str, Any]] = []
        seen_edges: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(label, 0)])

        while queue and len(visited_nodes) < max_nodes:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            edges = await self.get_node_edges(current)
            for src, tgt in edges:
                edge_key = f"{src}__{tgt}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edge_data = await self.get_edge(src, tgt)
                    if edge_data:
                        visited_edges.append(edge_data)

                neighbor = tgt if src == current else src
                if neighbor not in visited_nodes:
                    n_data = await self.get_node(neighbor)
                    if n_data:
                        visited_nodes[neighbor] = n_data
                        queue.append((neighbor, depth + 1))

        return {"nodes": list(visited_nodes.values()), "edges": visited_edges}

    async def _fetch_edges_for_nodes(
        self, node_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch all edges between the given node IDs."""
        if not node_ids:
            return []
        resp = await self._client.search(
            index=self._edges_index,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"terms": {"source_id": node_ids}},
                            {"terms": {"target_id": node_ids}},
                        ]
                    }
                },
                "size": 10000,
            },
        )
        out: list[dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            props = _deserialize_props(source.get("properties", {}))
            props["source_id"] = source["source_id"]
            props["target_id"] = source["target_id"]
            out.append(props)
        return out

    # ── Bulk ─────────────────────────────────────────────────────

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._nodes_index,
            body={"size": 100000, "query": {"match_all": {}}},
        )
        out: list[dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            props = _deserialize_props(source.get("properties", {}))
            props["id"] = hit["_id"]
            props["label"] = source.get("label", hit["_id"])
            out.append(props)
        return out

    async def get_all_edges(self) -> list[dict[str, Any]]:
        await self._ensure_indexes()
        resp = await self._client.search(
            index=self._edges_index,
            body={"size": 100000, "query": {"match_all": {}}},
        )
        out: list[dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            props = _deserialize_props(source.get("properties", {}))
            props["source_id"] = source.get("source_id", "")
            props["target_id"] = source.get("target_id", "")
            out.append(props)
        return out

    async def drop(self) -> None:
        for index_name in (self._nodes_index, self._edges_index):
            try:
                exists = await self._client.indices.exists(index=index_name)
                if exists:
                    await self._client.indices.delete(index=index_name)
            except Exception as exc:
                logger.warning("Failed to drop index %s: %s", index_name, exc)
        self._indexes_ready = False
