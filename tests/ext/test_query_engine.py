"""Unit tests for the 6-mode QueryEngine.

Tests each retrieval mode (naive, local, global, hybrid, mix, bypass)
with mock storages, plus keyword extraction, reranking, and helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aurora_core.model.base import BaseLLM
from aurora_core.rag.utils.embedding import EmbeddingFunc
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig
from aurora_ext.rag.retrieval.context_builder import QueryContext
from aurora_ext.rag.retrieval.query_engine import (
    QueryEngine,
    QueryMode,
    QueryParam,
    QueryResult,
)
from aurora_ext.rag.retrieval.reranker import RerankResult, RerankerBase
from aurora_ext.rag.storage.base import (
    BaseGraphStorage,
    BaseKVStorage,
    BaseVectorStorage,
)


# ── Fakes ─────────────────────────────────────────────────────────


class FakeLLM(BaseLLM):
    """Deterministic LLM stub for tests."""

    def __init__(self, response: str = "mock response") -> None:
        super().__init__(LLMConfig(model_name="fake", model_type="test"))
        self._response = response
        self.last_messages: list[Message] = []

    async def achat(self, messages: list[Message], **kwargs: Any) -> ModelOutput:
        self.last_messages = messages
        return ModelOutput(text=self._response)

    async def achat_stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ModelOutput]:
        self.last_messages = messages
        for word in self._response.split():
            yield ModelOutput(text=word + " ")


class FakeVectorStorage(BaseVectorStorage):
    """In-memory vector storage stub."""

    def __init__(
        self, results: list[dict] | None = None, *, supports_where_prefilter: bool = False
    ) -> None:
        super().__init__(namespace="test", global_config={})
        self._results = results or []
        self._supports_where_prefilter = supports_where_prefilter
        self.queries: list[dict[str, Any]] = []

    async def query(
        self,
        query: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.queries.append({
            "query": query,
            "top_k": top_k,
            "cosine_threshold": cosine_threshold,
            "where": where,
        })
        results = self._results
        if where and self._supports_where_prefilter:
            results = [
                r for r in results
                if all(r.get(k) == v for k, v in where.items())
            ]
        results = [r for r in results if r.get(
            "score", 1.0) >= cosine_threshold][:top_k]
        if where and not self._supports_where_prefilter:
            results = [
                r for r in results
                if all(r.get(k) == v for k, v in where.items())
            ]
        return results

    async def upsert(self, data: dict) -> None:
        pass

    async def delete(self, ids: list[str]) -> None:
        pass

    async def drop(self) -> None:
        pass


class FakeKVStorage(BaseKVStorage):
    """In-memory KV storage stub."""

    def __init__(self, data: dict[str, dict] | None = None) -> None:
        super().__init__(namespace="test", global_config={})
        self._data = data or {}

    async def all_keys(self) -> list[str]:
        return list(self._data.keys())

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        return self._data.get(key)

    async def get_by_ids(self, keys: list[str]) -> list[Optional[dict[str, Any]]]:
        return [self._data.get(k) for k in keys]

    async def get_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [v for v in self._data.values() if v.get(field) == value]

    async def upsert(self, data: dict) -> None:
        self._data.update(data)

    async def delete(self, keys: list[str]) -> None:
        for k in keys:
            self._data.pop(k, None)

    async def drop(self) -> None:
        self._data.clear()


class FakeGraphStorage(BaseGraphStorage):
    """In-memory graph storage stub."""

    def __init__(
        self,
        nodes: dict[str, dict] | None = None,
        edges: dict[tuple[str, str], dict] | None = None,
    ) -> None:
        super().__init__(namespace="test", global_config={})
        self._nodes = nodes or {}
        self._edges = edges or {}

    async def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        return self._nodes.get(node_id)

    async def upsert_node(self, node_id: str, node_data: dict) -> None:
        self._nodes[node_id] = node_data

    async def delete_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)

    async def node_degree(self, node_id: str) -> int:
        count = 0
        for src, tgt in self._edges:
            if src == node_id or tgt == node_id:
                count += 1
        return count

    async def get_all_labels(self) -> list[str]:
        return list(self._nodes.keys())

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        labels = sorted(
            self._nodes.keys(),
            key=lambda n: self.node_degree_sync(n),
            reverse=True,
        )
        return labels[:limit]

    def node_degree_sync(self, node_id: str) -> int:
        count = 0
        for src, tgt in self._edges:
            if src == node_id or tgt == node_id:
                count += 1
        return count

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        query_lower = query.lower()
        return [
            label
            for label in self._nodes
            if query_lower in label.lower()
        ][:limit]

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        return (source_id, target_id) in self._edges

    async def get_edge(self, source_id: str, target_id: str) -> Optional[dict]:
        return self._edges.get((source_id, target_id))

    async def upsert_edge(self, source_id: str, target_id: str, edge_data: dict) -> None:
        self._edges[(source_id, target_id)] = edge_data

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        self._edges.pop((source_id, target_id), None)

    async def edge_degree(self, source_id: str, target_id: str) -> int:
        return 1 if (source_id, target_id) in self._edges else 0

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        return [
            (src, tgt)
            for src, tgt in self._edges
            if src == node_id or tgt == node_id
        ]

    async def get_neighbors(self, node_id: str) -> list[str]:
        neighbors: set[str] = set()
        for src, tgt in self._edges:
            if src == node_id:
                neighbors.add(tgt)
            elif tgt == node_id:
                neighbors.add(src)
        return list(neighbors)

    async def get_connected_subgraph(
        self, label: str, max_depth: int = 3, max_nodes: int = 1000
    ) -> dict[str, Any]:
        return {"nodes": [], "edges": []}

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        return list(self._nodes.values())

    async def get_all_edges(self) -> list[dict[str, Any]]:
        return list(self._edges.values())

    async def drop(self) -> None:
        self._nodes.clear()
        self._edges.clear()


class FakeReranker(RerankerBase):
    """Deterministic reranker that reverses the document order."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        results = []
        for i, doc in enumerate(documents):
            score = 1.0 - (i * 0.1)
            if score >= min_score:
                results.append(RerankResult(index=i, score=score, content=doc))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_n]


# ── Fixtures ──────────────────────────────────────────────────────


def _build_test_data() -> tuple[dict, dict, dict]:
    """Build a consistent set of nodes, edges, and chunks for testing."""
    nodes = {
        "Python": {
            "entity_name": "Python",
            "entity_type": "Method",
            "description": "A programming language",
            "source_id": "chunk-1<SEP>chunk-2",
        },
        "FastAPI": {
            "entity_name": "FastAPI",
            "entity_type": "Artifact",
            "description": "A Python web framework",
            "source_id": "chunk-2<SEP>chunk-3",
        },
        "REST API": {
            "entity_name": "REST API",
            "entity_type": "Concept",
            "description": "Representational state transfer architecture",
            "source_id": "chunk-3<SEP>chunk-4",
        },
    }

    edges = {
        ("Python", "FastAPI"): {
            "source_entity": "Python",
            "target_entity": "FastAPI",
            "keywords": "powers,built-with",
            "description": "FastAPI is built with Python",
            "source_id": "chunk-2",
            "weight": 0.9,
        },
        ("FastAPI", "REST API"): {
            "source_entity": "FastAPI",
            "target_entity": "REST API",
            "keywords": "implements",
            "description": "FastAPI implements REST API patterns",
            "source_id": "chunk-3",
            "weight": 0.8,
        },
    }

    chunks = {
        "chunk-1": {
            "content": "Python is a versatile programming language.",
            "file_path": "python_intro.md",
            "id": "chunk-1",
        },
        "chunk-2": {
            "content": "FastAPI is a modern web framework for Python.",
            "file_path": "fastapi_guide.md",
            "id": "chunk-2",
        },
        "chunk-3": {
            "content": "FastAPI makes building REST APIs easy.",
            "file_path": "fastapi_guide.md",
            "id": "chunk-3",
        },
        "chunk-4": {
            "content": "REST API follows representational state transfer.",
            "file_path": "api_design.md",
            "id": "chunk-4",
        },
    }

    return nodes, edges, chunks


def _build_engine(
    nodes: dict | None = None,
    edges: dict | None = None,
    chunks: dict | None = None,
    vector_results: list[dict] | None = None,
    llm_response: str = "test response",
    reranker: RerankerBase | None = None,
) -> QueryEngine:
    """Assemble a QueryEngine with fake storages."""
    if nodes is None or edges is None or chunks is None:
        nodes, edges, chunks = _build_test_data()

    llm = FakeLLM(response=llm_response)
    embedding = MagicMock(spec=EmbeddingFunc)
    kv = FakeKVStorage(data=chunks)
    vector = FakeVectorStorage(results=vector_results or [])
    graph = FakeGraphStorage(nodes=nodes, edges=edges)

    return QueryEngine(
        llm=llm,
        embedding_func=embedding,
        kv_storage=kv,
        vector_storage=vector,
        graph_storage=graph,
        reranker=reranker,
    )


# ── QueryMode enum ────────────────────────────────────────────────


class TestQueryMode:
    def test_all_modes_defined(self):
        modes = {m.value for m in QueryMode}
        assert modes == {"local", "global", "hybrid", "naive", "mix", "bypass"}

    def test_string_enum(self):
        assert QueryMode.LOCAL == "local"
        assert QueryMode.MIX == "mix"


# ── QueryParam defaults ──────────────────────────────────────────


class TestQueryParam:
    def test_defaults(self):
        p = QueryParam(query="test")
        assert p.mode == QueryMode.MIX
        assert p.top_k == 40
        assert p.chunk_top_k == 20
        assert p.enable_rerank is False
        assert p.stream is False

    def test_custom_values(self):
        p = QueryParam(
            query="test",
            mode=QueryMode.LOCAL,
            top_k=10,
            hl_keywords=["AI"],
            ll_keywords=["GPT"],
        )
        assert p.mode == QueryMode.LOCAL
        assert p.top_k == 10
        assert p.hl_keywords == ["AI"]
        assert p.ll_keywords == ["GPT"]


# ── Bypass mode ──────────────────────────────────────────────────


class TestBypassMode:
    @pytest.mark.asyncio
    async def test_bypass_calls_llm_directly(self):
        engine = _build_engine(llm_response="Hello from bypass!")
        param = QueryParam(query="Hello!", mode=QueryMode.BYPASS)

        result = await engine.query(param)

        assert result.response == "Hello from bypass!"
        assert result.context is None
        assert result.entities == []
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_bypass_includes_conversation_history(self):
        engine = _build_engine()
        param = QueryParam(
            query="Follow-up question",
            mode=QueryMode.BYPASS,
            conversation_history=[
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"},
            ],
        )

        await engine.query(param)

        llm = engine._llm
        assert isinstance(llm, FakeLLM)
        # system + 2 history turns + current query = 4 messages
        assert len(llm.last_messages) == 3
        assert llm.last_messages[-1].content == "Follow-up question"
        assert llm.last_messages[0].content == "Previous question"


# ── Naive mode ────────────────────────────────────────────────────


class TestNaiveMode:
    @pytest.mark.asyncio
    async def test_naive_uses_vector_only(self):
        vector_results = [
            {"id": "chunk-1", "content": "Python is great",
                "file_path": "a.md", "score": 0.9},
            {"id": "chunk-2", "content": "FastAPI is modern",
                "file_path": "b.md", "score": 0.8},
        ]
        engine = _build_engine(vector_results=vector_results)
        param = QueryParam(
            query="Tell me about Python",
            mode=QueryMode.NAIVE,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.context is not None
        assert result.context.is_kg_mode is False
        assert len(result.chunks) == 2
        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_naive_no_keyword_extraction(self):
        engine = _build_engine(vector_results=[])
        engine._keyword_extractor = MagicMock()  # Should not be called
        param = QueryParam(query="test", mode=QueryMode.NAIVE,
                           only_need_context=True)

        await engine.query(param)

        engine._keyword_extractor.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_naive_empty_results(self):
        engine = _build_engine(vector_results=[])
        param = QueryParam(
            query="nothing", mode=QueryMode.NAIVE, only_need_context=True)

        result = await engine.query(param)

        assert result.chunks == []


# ── Local mode ────────────────────────────────────────────────────


class TestLocalMode:
    @pytest.mark.asyncio
    async def test_local_entity_search(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="Tell me about Python",
            mode=QueryMode.LOCAL,
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.context is not None
        assert result.context.is_kg_mode is True
        # Should find Python entity
        entity_names = [e.get("entity_name", "") for e in result.entities]
        assert "Python" in entity_names

    @pytest.mark.asyncio
    async def test_local_finds_neighbors(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="Python programming",
            mode=QueryMode.LOCAL,
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        # Python → FastAPI edge should be discovered
        entity_names = {e.get("entity_name", "") for e in result.entities}
        assert "FastAPI" in entity_names  # Neighbour of Python
        assert len(result.relationships) >= 1

    @pytest.mark.asyncio
    async def test_local_graph_label_search(self):
        nodes, edges, chunks = _build_test_data()
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=[],  # No vector results
        )
        param = QueryParam(
            query="FastAPI",
            mode=QueryMode.LOCAL,
            ll_keywords=["FastAPI"],
            only_need_context=True,
        )

        result = await engine.query(param)

        # Graph label search should find FastAPI
        entity_names = {e.get("entity_name", "") for e in result.entities}
        assert "FastAPI" in entity_names

    @pytest.mark.asyncio
    async def test_local_with_keywords_extraction(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )

        # Mock keyword extractor
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = (["Programming"], ["Python"])
        engine._keyword_extractor = mock_extractor

        param = QueryParam(
            query="Tell me about Python programming",
            mode=QueryMode.LOCAL,
            only_need_context=True,
        )

        result = await engine.query(param)

        mock_extractor.extract.assert_awaited_once_with(
            param.query, language="English")
        assert result.hl_keywords == ["Programming"]
        assert result.ll_keywords == ["Python"]


# ── Global mode ───────────────────────────────────────────────────


class TestGlobalMode:
    @pytest.mark.asyncio
    async def test_global_relation_search(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {
                "id": "rel-1",
                "source_entity": "Python",
                "target_entity": "FastAPI",
                "weight": 0.9,
                "source_id": "chunk-2",
            },
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="How does Python relate to FastAPI?",
            mode=QueryMode.GLOBAL,
            hl_keywords=["Python", "FastAPI", "relationship"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.context is not None
        assert result.context.is_kg_mode is True
        assert len(result.relationships) >= 1
        # Both endpoints should be resolved
        entity_names = {e.get("entity_name", "") for e in result.entities}
        assert "Python" in entity_names
        assert "FastAPI" in entity_names

    @pytest.mark.asyncio
    async def test_global_weight_sorting(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {
                "id": "rel-low",
                "source_entity": "FastAPI",
                "target_entity": "REST API",
                "weight": 0.3,
                "source_id": "chunk-3",
            },
            {
                "id": "rel-high",
                "source_entity": "Python",
                "target_entity": "FastAPI",
                "weight": 0.9,
                "source_id": "chunk-2",
            },
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="relationships",
            mode=QueryMode.GLOBAL,
            hl_keywords=["relationships"],
            only_need_context=True,
        )

        result = await engine.query(param)

        # High-weight relationship should come first
        assert len(result.relationships) >= 2


# ── Hybrid mode ───────────────────────────────────────────────────


class TestHybridMode:
    @pytest.mark.asyncio
    async def test_hybrid_merges_local_and_global(self):
        nodes, edges, chunks = _build_test_data()

        # Vector returns both entity and relation results
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
            {
                "id": "rel-1",
                "source_entity": "FastAPI",
                "target_entity": "REST API",
                "weight": 0.8,
                "source_id": "chunk-3",
            },
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="Python and REST APIs",
            mode=QueryMode.HYBRID,
            hl_keywords=["APIs"],
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.context is not None
        assert result.context.is_kg_mode is True
        # Should have entities from both local and global paths
        entity_names = {e.get("entity_name", "") for e in result.entities}
        assert "Python" in entity_names

    @pytest.mark.asyncio
    async def test_hybrid_deduplicates(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="Python",
            mode=QueryMode.HYBRID,
            hl_keywords=["Python"],
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        # No duplicate entities
        entity_names = [e.get("entity_name", "") for e in result.entities]
        assert len(entity_names) == len(set(entity_names))


# ── Mix mode ──────────────────────────────────────────────────────


class TestMixMode:
    @pytest.mark.asyncio
    async def test_mix_combines_kg_and_naive(self):
        nodes, edges, chunks = _build_test_data()

        # Add extra chunks for naive vector search
        chunks["chunk-5"] = {
            "content": "Microservices architecture overview",
            "file_path": "architecture.md",
            "id": "chunk-5",
        }

        # Vector results serve both entity search AND naive chunk search
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
            {"id": "chunk-5", "content": "Microservices architecture overview",
             "file_path": "architecture.md", "score": 0.7},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="Tell me about Python and microservices",
            mode=QueryMode.MIX,
            hl_keywords=["microservices"],
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.context is not None
        assert result.context.is_kg_mode is True
        # Should have both KG entities and naive chunks
        assert len(result.entities) >= 1
        assert len(result.chunks) >= 1

    @pytest.mark.asyncio
    async def test_mix_default_mode(self):
        """MIX is the default mode."""
        param = QueryParam(query="test")
        assert param.mode == QueryMode.MIX


# ── Keyword extraction integration ───────────────────────────────


class TestKeywordExtraction:
    @pytest.mark.asyncio
    async def test_keywords_extracted_when_not_provided(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )

        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = (["Programming"], ["Python"])
        engine._keyword_extractor = mock_extractor

        param = QueryParam(
            query="Python programming",
            mode=QueryMode.LOCAL,
            only_need_context=True,
        )

        await engine.query(param)
        mock_extractor.extract.assert_awaited_once_with(
            "Python programming", language="English")

    @pytest.mark.asyncio
    async def test_keywords_not_extracted_for_naive(self):
        engine = _build_engine(vector_results=[])
        mock_extractor = AsyncMock()
        engine._keyword_extractor = mock_extractor

        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            only_need_context=True,
        )

        await engine.query(param)
        mock_extractor.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_pre_provided_keywords_used(self):
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
        ]
        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
        )
        mock_extractor = AsyncMock()
        engine._keyword_extractor = mock_extractor

        param = QueryParam(
            query="Python",
            mode=QueryMode.LOCAL,
            hl_keywords=["Programming"],
            ll_keywords=["Python"],
            only_need_context=True,
        )

        result = await engine.query(param)

        # Should not call extractor when keywords are pre-provided
        mock_extractor.extract.assert_not_called()
        assert result.hl_keywords == ["Programming"]
        assert result.ll_keywords == ["Python"]


# ── Reranking ─────────────────────────────────────────────────────


class TestReranking:
    @pytest.mark.asyncio
    async def test_rerank_applied_when_enabled(self):
        vector_results = [
            {"id": "chunk-1", "content": "A", "file_path": "a.md", "score": 0.9},
            {"id": "chunk-2", "content": "B", "file_path": "b.md", "score": 0.8},
            {"id": "chunk-3", "content": "C", "file_path": "c.md", "score": 0.7},
        ]
        engine = _build_engine(
            vector_results=vector_results,
            reranker=FakeReranker(),
        )
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            enable_rerank=True,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert len(result.chunks) == 3
        # FakeReranker assigns scores 1.0, 0.9, 0.8 in order
        assert result.chunks[0].get("rerank_score") is not None

    @pytest.mark.asyncio
    async def test_rerank_skipped_when_disabled(self):
        vector_results = [
            {"id": "chunk-1", "content": "A", "file_path": "a.md", "score": 0.9},
        ]
        engine = _build_engine(
            vector_results=vector_results,
            reranker=FakeReranker(),
        )
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            enable_rerank=False,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.chunks[0].get("rerank_score") is None

    @pytest.mark.asyncio
    async def test_rerank_skipped_when_no_reranker(self):
        vector_results = [
            {"id": "chunk-1", "content": "A", "file_path": "a.md", "score": 0.9},
        ]
        engine = _build_engine(
            vector_results=vector_results,
            reranker=None,
        )
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            enable_rerank=True,
            only_need_context=True,
        )

        result = await engine.query(param)

        # Should not crash
        assert len(result.chunks) == 1


# ── only_need_context / only_need_prompt ─────────────────────────


class TestOutputModes:
    @pytest.mark.asyncio
    async def test_only_need_context(self):
        vector_results = [
            {"id": "chunk-1", "content": "Hello",
                "file_path": "a.md", "score": 0.9},
        ]
        engine = _build_engine(vector_results=vector_results)
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert result.response == ""
        assert result.context is not None

    @pytest.mark.asyncio
    async def test_only_need_prompt(self):
        vector_results = [
            {"id": "chunk-1", "content": "Hello",
                "file_path": "a.md", "score": 0.9},
        ]
        engine = _build_engine(vector_results=vector_results)
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            only_need_prompt=True,
        )

        result = await engine.query(param)

        # Should contain the prompt, not a generated response
        assert len(result.response) > 0
        assert "Context" in result.response or "context" in result.response.lower()


# ── Dedup helpers ─────────────────────────────────────────────────


class TestDedupHelpers:
    def test_merge_dedup_entities(self):
        a = [{"entity_name": "Python", "desc": "lang"}]
        b = [{"entity_name": "Python", "desc": "language"},
             {"entity_name": "FastAPI"}]
        result = QueryEngine._merge_dedup_entities(a, b)
        names = [e["entity_name"] for e in result]
        assert names == ["Python", "FastAPI"]

    def test_merge_dedup_relations(self):
        a = [{"source_entity": "A", "target_entity": "B"}]
        b = [
            {"source_entity": "A", "target_entity": "B"},
            {"source_entity": "C", "target_entity": "D"},
        ]
        result = QueryEngine._merge_dedup_relations(a, b)
        assert len(result) == 2

    def test_merge_dedup_chunks(self):
        a = [{"chunk_id": "c1", "content": "hello"}]
        b = [{"chunk_id": "c1", "content": "hello"},
             {"chunk_id": "c2", "content": "world"}]
        result = QueryEngine._merge_dedup_chunks(a, b)
        assert len(result) == 2

    def test_merge_dedup_entities_empty(self):
        assert QueryEngine._merge_dedup_entities([], []) == []

    def test_merge_dedup_relations_empty(self):
        assert QueryEngine._merge_dedup_relations([], []) == []


# ── pick_chunk_ids ───────────────────────────────────────────────


class TestPickChunkIds:
    def test_vector_mode_takes_last_n(self):
        source_ids = "a<SEP>b<SEP>c<SEP>d<SEP>e"
        result = QueryEngine._pick_chunk_ids(source_ids, 3, "VECTOR")
        assert result == {"c", "d", "e"}

    def test_weight_mode_takes_first_n(self):
        source_ids = "a<SEP>b<SEP>c<SEP>d<SEP>e"
        result = QueryEngine._pick_chunk_ids(source_ids, 3, "WEIGHT")
        assert result == {"a", "b", "c"}

    def test_empty_source_ids(self):
        assert QueryEngine._pick_chunk_ids("", 5) == set()

    def test_fewer_ids_than_requested(self):
        source_ids = "a<SEP>b"
        result = QueryEngine._pick_chunk_ids(source_ids, 10, "VECTOR")
        assert result == {"a", "b"}

    def test_whitespace_handling(self):
        source_ids = " a <SEP> b <SEP> c "
        result = QueryEngine._pick_chunk_ids(source_ids, 2, "VECTOR")
        assert result == {"b", "c"}


# ── Conversation history ─────────────────────────────────────────


class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_history_included_in_messages(self):
        engine = _build_engine(vector_results=[], llm_response="response")
        param = QueryParam(
            query="What about FastAPI?",
            mode=QueryMode.NAIVE,
            conversation_history=[
                {"role": "user", "content": "Tell me about Python"},
                {"role": "assistant", "content": "Python is a language"},
            ],
        )

        await engine.query(param)

        llm = engine._llm
        assert isinstance(llm, FakeLLM)
        # system_prompt + user_history + assistant_history + query
        assert len(llm.last_messages) == 4

    @pytest.mark.asyncio
    async def test_empty_history(self):
        engine = _build_engine(vector_results=[], llm_response="response")
        param = QueryParam(query="Hello", mode=QueryMode.NAIVE)

        await engine.query(param)

        llm = engine._llm
        assert isinstance(llm, FakeLLM)
        # system_prompt + query only
        assert len(llm.last_messages) == 2


# ── Streaming ─────────────────────────────────────────────────────


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_returns_iterator(self):
        vector_results = [
            {"id": "chunk-1", "content": "Hello",
                "file_path": "a.md", "score": 0.9},
        ]
        engine = _build_engine(
            vector_results=vector_results, llm_response="hello world")
        param = QueryParam(
            query="test",
            mode=QueryMode.NAIVE,
            stream=True,
        )

        result = await engine.query(param)

        assert result.is_streaming is True
        assert result.stream_iterator is not None

        # Consume the stream
        parts = []
        async for chunk in result.stream_iterator:
            parts.append(chunk)

        assert len(parts) >= 1


# ── Full pipeline ─────────────────────────────────────────────────


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_mix_full_pipeline(self):
        """End-to-end: MIX mode with keywords, rerank, and generation."""
        nodes, edges, chunks = _build_test_data()
        chunks["chunk-5"] = {
            "content": "Extra context from naive search",
            "file_path": "extra.md",
            "id": "chunk-5",
        }

        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
            {"id": "chunk-5", "content": "Extra context from naive search",
             "file_path": "extra.md", "score": 0.7},
        ]

        engine = _build_engine(
            nodes=nodes,
            edges=edges,
            chunks=chunks,
            vector_results=vector_results,
            llm_response="Python is a programming language used for web development.",
            reranker=FakeReranker(),
        )

        param = QueryParam(
            query="What is Python used for?",
            mode=QueryMode.MIX,
            hl_keywords=["Python", "usage"],
            ll_keywords=["Python"],
            enable_rerank=True,
        )

        result = await engine.query(param)

        assert result.response == "Python is a programming language used for web development."
        assert result.context is not None
        assert len(result.entities) >= 1
        assert len(result.chunks) >= 1
        assert result.hl_keywords == ["Python", "usage"]
        assert result.ll_keywords == ["Python"]

    @pytest.mark.asyncio
    async def test_all_modes_produce_results(self):
        """Smoke test: every mode returns a non-empty result."""
        nodes, edges, chunks = _build_test_data()
        vector_results = [
            {"id": "Python", "entity_name": "Python", "score": 0.95},
            {"id": "chunk-1", "content": "Python is great",
             "file_path": "a.md", "score": 0.9},
        ]

        for mode in QueryMode:
            engine = _build_engine(
                nodes=nodes,
                edges=edges,
                chunks=chunks,
                vector_results=vector_results,
                llm_response=f"response for {mode.value}",
            )
            param = QueryParam(
                query="test query",
                mode=mode,
                hl_keywords=["test"],
                ll_keywords=["query"],
            )

            result = await engine.query(param)
            assert result.response, f"Mode {mode.value} returned empty response"


class TestKnowledgeBaseScoping:
    @pytest.mark.asyncio
    async def test_naive_filters_vector_results_to_current_knowledge_base(self):
        engine = _build_engine(
            vector_results=[
                {
                    "id": "kb-other:chunk:doc:0",
                    "content": "unrelated result from another KB",
                    "file_path": "other.md",
                    "score": 0.99,
                },
                {
                    "id": "kb-current:chunk:doc:0",
                    "content": "current KB result",
                    "file_path": "current.md",
                    "score": 0.8,
                },
            ]
        )
        param = QueryParam(
            query="shared query",
            mode=QueryMode.NAIVE,
            kb_name="kb-current",
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [c["chunk_id"]
                for c in result.chunks] == ["kb-current:chunk:doc:0"]
        assert result.chunks[0]["content"] == "current KB result"

    @pytest.mark.asyncio
    async def test_local_graph_label_search_is_scoped_to_current_knowledge_base(self):
        nodes = {
            "kb-current:FastAPI": {
                "entity_name": "FastAPI",
                "entity_type": "Artifact",
                "description": "Current KB FastAPI",
                "source_id": "kb-current:text_chunks:doc:0",
            },
            "kb-other:FastAPI": {
                "entity_name": "FastAPI",
                "entity_type": "Artifact",
                "description": "Other KB FastAPI",
                "source_id": "kb-other:text_chunks:doc:0",
            },
        }
        chunks = {
            "kb-current:text_chunks:doc:0": {
                "content": "Current KB chunk",
                "file_path": "current.md",
                "id": "kb-current:text_chunks:doc:0",
            },
            "kb-other:text_chunks:doc:0": {
                "content": "Other KB chunk",
                "file_path": "other.md",
                "id": "kb-other:text_chunks:doc:0",
            },
        }
        engine = _build_engine(nodes=nodes, edges={},
                               chunks=chunks, vector_results=[])
        param = QueryParam(
            query="FastAPI",
            mode=QueryMode.LOCAL,
            kb_name="kb-current",
            ll_keywords=["FastAPI"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [e["description"]
                for e in result.entities] == ["Current KB FastAPI"]
        assert [c["content"] for c in result.chunks] == ["Current KB chunk"]

    @pytest.mark.asyncio
    async def test_naive_overfetches_before_filtering_to_current_knowledge_base(self):
        engine = _build_engine(
            vector_results=[
                {
                    "id": "kb-other:chunk:doc:0",
                    "content": "higher ranked other KB result",
                    "file_path": "other.md",
                    "score": 0.99,
                },
                {
                    "id": "kb-current:chunk:doc:0",
                    "content": "lower ranked current KB result",
                    "file_path": "current.md",
                    "score": 0.8,
                },
            ]
        )
        param = QueryParam(
            query="shared query",
            mode=QueryMode.NAIVE,
            kb_name="kb-current",
            chunk_top_k=1,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [c["chunk_id"]
                for c in result.chunks] == ["kb-current:chunk:doc:0"]

    @pytest.mark.asyncio
    async def test_local_overfetches_labels_before_filtering_to_current_knowledge_base(self):
        nodes = {
            "kb-other:FastAPI": {
                "entity_name": "FastAPI",
                "entity_type": "Artifact",
                "description": "Other KB FastAPI",
                "source_id": "kb-other:text_chunks:doc:0",
            },
            "kb-current:FastAPI": {
                "entity_name": "FastAPI",
                "entity_type": "Artifact",
                "description": "Current KB FastAPI",
                "source_id": "kb-current:text_chunks:doc:0",
            },
        }
        chunks = {
            "kb-current:text_chunks:doc:0": {
                "content": "Current KB chunk",
                "file_path": "current.md",
                "id": "kb-current:text_chunks:doc:0",
            },
            "kb-other:text_chunks:doc:0": {
                "content": "Other KB chunk",
                "file_path": "other.md",
                "id": "kb-other:text_chunks:doc:0",
            },
        }
        engine = _build_engine(nodes=nodes, edges={},
                               chunks=chunks, vector_results=[])
        param = QueryParam(
            query="FastAPI",
            mode=QueryMode.LOCAL,
            kb_name="kb-current",
            top_k=1,
            ll_keywords=["FastAPI"],
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [e["description"]
                for e in result.entities] == ["Current KB FastAPI"]

    @pytest.mark.asyncio
    async def test_mix_does_not_treat_entity_vectors_as_naive_chunks(self):
        nodes = {
            "kb:配方模板功能": {
                "entity_name": "配方模板功能",
                "entity_type": "concept",
                "description": "提供可复用的配方参数骨架",
                "source_id": "kb:text_chunks:formula:0",
            },
            "kb:Workflow": {
                "entity_name": "Workflow",
                "entity_type": "concept",
                "description": "企业业务流程编排",
                "source_id": "kb:text_chunks:workflow:0",
            },
        }
        chunks = {
            "kb:text_chunks:formula:0": {
                "content": "配方模板提供可复用的配方参数骨架。",
                "file_path": "配方模板.txt",
                "id": "kb:text_chunks:formula:0",
            },
            "kb:text_chunks:workflow:0": {
                "content": "Workflow 用于复杂业务流程编排。",
                "file_path": "workflow.txt",
                "id": "kb:text_chunks:workflow:0",
            },
        }
        vector_results = [
            {
                "id": "kb:配方模板功能",
                "entity_name": "配方模板功能",
                "entity_type": "concept",
                "description": "提供可复用的配方参数骨架",
                "kind": "entity",
                "score": 0.95,
            },
            {
                "id": "kb:Workflow",
                "entity_name": "Workflow",
                "entity_type": "concept",
                "description": "企业业务流程编排",
                "kind": "entity",
                "score": 0.90,
            },
            {
                "id": "kb:text_chunks:formula:0",
                "content": "配方模板提供可复用的配方参数骨架。",
                "file_path": "配方模板.txt",
                "kind": "chunk",
                "score": 0.80,
            },
            {
                "id": "kb:text_chunks:workflow:0",
                "content": "Workflow 用于复杂业务流程编排。",
                "file_path": "workflow.txt",
                "kind": "chunk",
                "score": 0.70,
            },
        ]
        engine = _build_engine(
            nodes=nodes,
            edges={},
            chunks=chunks,
            vector_results=vector_results,
        )
        param = QueryParam(
            query="配方模板是什么",
            mode=QueryMode.MIX,
            kb_name="kb",
            ll_keywords=["配方模板"],
            chunk_top_k=10,
            only_need_context=True,
        )

        result = await engine.query(param)

        # KG path should only resolve 配方模板 entity's chunk
        # Naive path may return both chunks (broad vector similarity).
        # The key guarantee: no entity vectors leak into the chunk list.
        file_paths = {c["file_path"] for c in result.chunks}
        assert "配方模板.txt" in file_paths
        # Entity vectors must NOT appear as chunks
        for c in result.chunks:
            assert "entity_name" not in c, f"Entity vector leaked into chunks: {c}"


class TestVectorKindFiltering:
    @pytest.mark.asyncio
    async def test_naive_filters_vector_kind_before_top_k_is_applied(self):
        vector_results = [
            {
                "id": f"kb:entity:{i}",
                "entity_name": f"Entity {i}",
                "description": "entity result",
                "kind": "entity",
                "score": 0.99,
            }
            for i in range(120)
        ] + [
            {
                "id": "kb:chunk:doc:0",
                "content": "Relevant chunk after many entity vectors",
                "file_path": "relevant.md",
                "kind": "chunk",
                "score": 0.8,
            }
        ]
        vector = FakeVectorStorage(
            vector_results, supports_where_prefilter=True)
        engine = _build_engine(vector_results=[])
        engine._vector = vector
        param = QueryParam(
            query="Relevant",
            mode=QueryMode.NAIVE,
            kb_name="kb",
            chunk_top_k=1,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [c["chunk_id"] for c in result.chunks] == ["kb:chunk:doc:0"]
        assert any(q["where"] == {"kind": "chunk"} for q in vector.queries)

    @pytest.mark.asyncio
    async def test_local_filters_entity_kind_before_top_k_is_applied(self):
        nodes = {
            "kb:配方模板": {
                "entity_name": "配方模板",
                "entity_type": "concept",
                "description": "模板",
                "source_id": "kb:text_chunks:doc:0",
            }
        }
        chunks = {
            "kb:text_chunks:doc:0": {
                "content": "配方模板内容",
                "file_path": "配方模板.txt",
                "id": "kb:text_chunks:doc:0",
            }
        }
        vector_results = [
            {
                "id": f"kb:chunk:other:{i}",
                "content": "chunk noise",
                "file_path": "noise.md",
                "kind": "chunk",
                "score": 0.99,
            }
            for i in range(120)
        ] + [
            {
                "id": "kb:配方模板",
                "entity_name": "配方模板",
                "description": "模板",
                "kind": "entity",
                "score": 0.8,
            }
        ]
        vector = FakeVectorStorage(
            vector_results, supports_where_prefilter=True)
        engine = _build_engine(nodes=nodes, edges={},
                               chunks=chunks, vector_results=[])
        engine._vector = vector
        param = QueryParam(
            query="配方模板",
            mode=QueryMode.LOCAL,
            kb_name="kb",
            top_k=1,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [e["entity_name"] for e in result.entities] == ["配方模板"]
        assert any(q["where"] == {"kind": "entity"} for q in vector.queries)

    @pytest.mark.asyncio
    async def test_mix_deduplicates_vector_chunk_against_kg_text_chunk(self):
        nodes = {
            "kb:配方模板": {
                "entity_name": "配方模板",
                "entity_type": "concept",
                "description": "模板",
                "source_id": "kb:text_chunks:doc:0",
            }
        }
        chunks = {
            "kb:text_chunks:doc:0": {
                "content": "配方模板内容",
                "file_path": "配方模板.txt",
                "id": "kb:text_chunks:doc:0",
            }
        }
        vector_results = [
            {
                "id": "kb:chunk:doc:0",
                "content": "配方模板内容",
                "file_path": "配方模板.txt",
                "kind": "chunk",
                "score": 0.8,
            },
            {
                "id": "kb:配方模板",
                "entity_name": "配方模板",
                "description": "模板",
                "kind": "entity",
                "score": 0.9,
            },
        ]
        engine = _build_engine(
            nodes=nodes, edges={}, chunks=chunks, vector_results=vector_results
        )
        param = QueryParam(
            query="配方模板是什么",
            mode=QueryMode.MIX,
            kb_name="kb",
            ll_keywords=["配方模板"],
            chunk_top_k=10,
            only_need_context=True,
        )

        result = await engine.query(param)

        assert [c["chunk_id"]
                for c in result.chunks] == ["kb:text_chunks:doc:0"]
        assert [r["file_path"] for r in result.references] == ["配方模板.txt"]
