"""NetworkX-backed graph storage.

Migrated from LightRAG ``kg/networkx_impl.py``.

The graph is persisted as a GraphML file at
``{working_dir}/{namespace}.graphml``.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from typing import Any, Optional

import networkx as nx

from aurora_ext.rag.storage.base import BaseGraphStorage

logger = logging.getLogger(__name__)


class NetworkXGraphStorage(BaseGraphStorage):
    """NetworkX-based local graph storage with GraphML persistence."""

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        working_dir = global_config.get("working_dir", "./rag_storage")
        self._file_path = os.path.join(working_dir, f"{namespace}.graphml")
        self._graph = nx.Graph()
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self._file_path):
            try:
                self._graph = nx.read_graphml(self._file_path)
            except Exception as exc:
                logger.warning("Failed to load graph %s: %s", self._file_path, exc)
                self._graph = nx.Graph()
        self._loaded = True

    async def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        nx.write_graphml(self._graph, self._file_path)

    # ── Node operations ──────────────────────────────────────────

    async def has_node(self, node_id: str) -> bool:
        await self._ensure_loaded()
        return self._graph.has_node(node_id)

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        await self._ensure_loaded()
        if not self._graph.has_node(node_id):
            return None
        data = dict(self._graph.nodes[node_id])
        data["id"] = node_id
        return data

    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        await self._ensure_loaded()
        safe_data = {}
        for k, v in node_data.items():
            if isinstance(v, (list, dict)):
                safe_data[k] = str(v)
            else:
                safe_data[k] = v
        self._graph.add_node(node_id, **safe_data)
        await self._persist()

    async def delete_node(self, node_id: str) -> None:
        await self._ensure_loaded()
        if self._graph.has_node(node_id):
            self._graph.remove_node(node_id)
            await self._persist()

    async def node_degree(self, node_id: str) -> int:
        await self._ensure_loaded()
        if not self._graph.has_node(node_id):
            return 0
        return self._graph.degree(node_id)

    async def get_all_labels(self) -> list[str]:
        await self._ensure_loaded()
        return list(self._graph.nodes())

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        await self._ensure_loaded()
        degrees = sorted(self._graph.degree(), key=lambda x: x[1], reverse=True)
        return [node for node, _ in degrees[:limit]]

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        await self._ensure_loaded()
        query_lower = query.lower().strip()

        if not query_lower:
            return []

        # Collect matching nodes with relevance scores
        matches = []
        for node in self._graph.nodes():
            node_str = str(node)
            node_lower = node_str.lower()

            # Skip if no match
            if query_lower not in node_lower:
                continue

            # Calculate relevance score
            # Exact match gets highest score
            if node_lower == query_lower:
                score = 1000
            # Prefix match gets high score
            elif node_lower.startswith(query_lower):
                score = 500
            # Contains match gets base score, with bonus for shorter strings
            else:
                # Shorter strings with matches are more relevant
                score = 100 - len(node_str)
                # Bonus for word boundary matches
                if f" {query_lower}" in node_lower or f"_{query_lower}" in node_lower:
                    score += 50
                    
            matches.append((node_str, score))

        # Sort by score descending and return top limit
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:limit]]

    # ── Edge operations ──────────────────────────────────────────

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        await self._ensure_loaded()
        return self._graph.has_edge(source_id, target_id)

    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_loaded()
        if not self._graph.has_edge(source_id, target_id):
            return None
        data = dict(self._graph.edges[source_id, target_id])
        data["source_id"] = source_id
        data["target_id"] = target_id
        return data

    async def upsert_edge(
        self, source_id: str, target_id: str, edge_data: dict[str, Any]
    ) -> None:
        await self._ensure_loaded()
        safe_data = {}
        for k, v in edge_data.items():
            if isinstance(v, (list, dict)):
                safe_data[k] = str(v)
            else:
                safe_data[k] = v
        self._graph.add_edge(source_id, target_id, **safe_data)
        await self._persist()

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        await self._ensure_loaded()
        if self._graph.has_edge(source_id, target_id):
            self._graph.remove_edge(source_id, target_id)
            await self._persist()

    async def edge_degree(self, source_id: str, target_id: str) -> int:
        await self._ensure_loaded()
        if not self._graph.has_edge(source_id, target_id):
            return 0
        return int(self._graph.edges[source_id, target_id].get("weight", 1))

    # ── Traversal ────────────────────────────────────────────────

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        await self._ensure_loaded()
        if not self._graph.has_node(node_id):
            return []
        return list(self._graph.edges(node_id))

    async def get_neighbors(self, node_id: str) -> list[str]:
        await self._ensure_loaded()
        if not self._graph.has_node(node_id):
            return []
        return list(self._graph.neighbors(node_id))

    async def get_connected_subgraph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """BFS traversal from *label* up to *max_depth* and *max_nodes*."""
        await self._ensure_loaded()

        # Handle wildcard: return top nodes by degree
        if label == "*":
            if self._graph.number_of_nodes() == 0:
                return {"nodes": [], "edges": []}

            degrees = dict(self._graph.degree())
            sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
            limited_nodes = [node for node, _ in sorted_nodes[:max_nodes]]

            subgraph = self._graph.subgraph(limited_nodes)
            nodes_out: list[dict[str, Any]] = []
            for nid in subgraph.nodes():
                ndata = dict(subgraph.nodes[nid])
                ndata["id"] = nid
                nodes_out.append(ndata)

            edges_out: list[dict[str, Any]] = []
            for src, tgt in subgraph.edges():
                edata = dict(subgraph.edges[src, tgt])
                edata["source_id"] = src
                edata["target_id"] = tgt
                edges_out.append(edata)

            return {"nodes": nodes_out, "edges": edges_out}

        if not self._graph.has_node(label):
            return {"nodes": [], "edges": []}

        visited_nodes: set[str] = set()
        visited_edges: set[tuple[str, str]] = set()
        queue: deque[tuple[str, int]] = deque([(label, 0)])

        while queue and len(visited_nodes) < max_nodes:
            current, depth = queue.popleft()
            if current in visited_nodes:
                continue
            visited_nodes.add(current)

            if depth < max_depth:
                for neighbor in self._graph.neighbors(current):
                    edge = tuple(sorted([current, neighbor]))
                    visited_edges.add(edge)
                    if neighbor not in visited_nodes:
                        queue.append((neighbor, depth + 1))

        nodes_out: list[dict[str, Any]] = []
        for nid in visited_nodes:
            ndata = dict(self._graph.nodes[nid])
            ndata["id"] = nid
            nodes_out.append(ndata)

        edges_out: list[dict[str, Any]] = []
        for src, tgt in visited_edges:
            if src in visited_nodes and tgt in visited_nodes:
                edata = dict(self._graph.edges[src, tgt])
                edata["source_id"] = src
                edata["target_id"] = tgt
                edges_out.append(edata)

        return {"nodes": nodes_out, "edges": edges_out}

    # ── Bulk ─────────────────────────────────────────────────────

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        await self._ensure_loaded()
        out = []
        for nid in self._graph.nodes():
            ndata = dict(self._graph.nodes[nid])
            ndata["id"] = nid
            out.append(ndata)
        return out

    async def get_all_edges(self) -> list[dict[str, Any]]:
        await self._ensure_loaded()
        out = []
        for src, tgt in self._graph.edges():
            edata = dict(self._graph.edges[src, tgt])
            edata["source_id"] = src
            edata["target_id"] = tgt
            out.append(edata)
        return out

    async def drop(self) -> None:
        self._graph = nx.Graph()
        if os.path.exists(self._file_path):
            os.remove(self._file_path)
