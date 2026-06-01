"""Query engine — 6 retrieval modes combining KG + vector search.

Migrated from LightRAG ``operate.py`` query functions:
  - ``kg_query()``  (local/global/hybrid/mix)
  - ``naive_query()`` (vector-only)
  - bypass mode (direct LLM)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

from aurora_core.model.base import BaseLLM
from aurora_core.rag.utils.embedding import EmbeddingFunc
from aurora_core.schema.message import Message
from aurora_ext.rag.extraction.prompts import PROMPTS
from aurora_ext.rag.retrieval.context_builder import ContextBuilder, QueryContext
from aurora_ext.rag.retrieval.keyword_extractor import KeywordExtractor
from aurora_ext.rag.retrieval.reranker import RerankerBase
from aurora_ext.rag.retrieval.token_budget import TokenBudget
from aurora_ext.rag.storage.base import BaseGraphStorage, BaseKVStorage, BaseVectorStorage

logger = logging.getLogger(__name__)


class QueryMode(str, Enum):
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    NAIVE = "naive"
    MIX = "mix"
    BYPASS = "bypass"


@dataclass
class QueryParam:
    """Full query parameter set — migrated from LightRAG.

    All 18 parameters as documented in the migration plan.
    """

    query: str
    mode: QueryMode = QueryMode.MIX
    only_need_context: bool = False
    only_need_prompt: bool = False
    response_type: str = "Multiple Paragraphs"
    top_k: int = 40
    chunk_top_k: int = 20
    max_entity_tokens: int = 6000
    max_relation_tokens: int = 8000
    max_total_tokens: int = 30000
    hl_keywords: list[str] = field(default_factory=list)
    ll_keywords: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    user_prompt: Optional[str] = None
    enable_rerank: bool = False
    include_references: bool = True
    include_chunk_content: bool = False
    stream: bool = False


@dataclass
class QueryResult:
    """Query result — response text + structured data."""

    response: str = ""
    context: Optional[QueryContext] = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    hl_keywords: list[str] = field(default_factory=list)
    ll_keywords: list[str] = field(default_factory=list)
    is_streaming: bool = False
    stream_iterator: Optional[AsyncIterator[str]] = None


class QueryEngine:
    """Dual-level retrieval engine with 6 query modes.

    Combines knowledge graph traversal with vector similarity search.
    """

    def __init__(
        self,
        llm: BaseLLM,
        embedding_func: EmbeddingFunc,
        kv_storage: BaseKVStorage,
        vector_storage: BaseVectorStorage,
        graph_storage: BaseGraphStorage,
        reranker: Optional[RerankerBase] = None,
    ) -> None:
        self._llm = llm
        self._embedding = embedding_func
        self._kv = kv_storage
        self._vector = vector_storage
        self._graph = graph_storage
        self._reranker = reranker
        self._keyword_extractor = KeywordExtractor(llm)
        self._context_builder = ContextBuilder()

    async def query(self, param: QueryParam) -> QueryResult:
        """Execute a query using the specified mode."""
        mode = param.mode

        if mode == QueryMode.BYPASS:
            return await self._bypass_query(param)

        # Extract keywords if not provided
        hl_kw, ll_kw = param.hl_keywords, param.ll_keywords
        if not hl_kw and not ll_kw and mode != QueryMode.NAIVE:
            hl_kw, ll_kw = await self._keyword_extractor.extract(param.query)

        # Route to appropriate retriever
        if mode == QueryMode.NAIVE:
            ctx = await self._naive_retrieve(param)
        elif mode == QueryMode.LOCAL:
            ctx = await self._local_retrieve(param, hl_kw, ll_kw)
        elif mode == QueryMode.GLOBAL:
            ctx = await self._global_retrieve(param, hl_kw, ll_kw)
        elif mode == QueryMode.HYBRID:
            ctx = await self._hybrid_retrieve(param, hl_kw, ll_kw)
        elif mode == QueryMode.MIX:
            ctx = await self._mix_retrieve(param, hl_kw, ll_kw)
        else:
            ctx = await self._naive_retrieve(param)

        # Apply reranking if enabled
        if param.enable_rerank and self._reranker and ctx.chunks:
            ctx = await self._apply_rerank(param, ctx)

        # Return context-only if requested
        if param.only_need_context:
            return QueryResult(
                context=ctx,
                entities=ctx.entities,
                relationships=ctx.relationships,
                chunks=ctx.chunks,
                references=ctx.references,
                hl_keywords=hl_kw,
                ll_keywords=ll_kw,
            )

        # Build prompt and generate response
        prompt = self._build_response_prompt(param, ctx)

        if param.only_need_prompt:
            return QueryResult(response=prompt, context=ctx)

        if param.stream:
            iterator = self._stream_generate(param, prompt)
            return QueryResult(
                context=ctx,
                is_streaming=True,
                stream_iterator=iterator,
                entities=ctx.entities,
                relationships=ctx.relationships,
                chunks=ctx.chunks,
                references=ctx.references,
                hl_keywords=hl_kw,
                ll_keywords=ll_kw,
            )

        response = await self._generate(param, prompt)
        return QueryResult(
            response=response,
            context=ctx,
            entities=ctx.entities,
            relationships=ctx.relationships,
            chunks=ctx.chunks,
            references=ctx.references,
            hl_keywords=hl_kw,
            ll_keywords=ll_kw,
        )

    # ── Bypass mode ──────────────────────────────────────────────

    async def _bypass_query(self, param: QueryParam) -> QueryResult:
        """Direct LLM pass-through, no retrieval."""
        messages = self._build_conversation_messages(param)
        output = await self._llm.achat(messages)
        return QueryResult(response=output.text)

    # ── Naive mode (vector-only) ─────────────────────────────────

    async def _naive_retrieve(
        self, param: QueryParam
    ) -> QueryContext:
        """Pure vector similarity search on chunks — no KG."""
        results = await self._vector.query(
            param.query,
            top_k=param.chunk_top_k,
        )

        chunks = [
            {
                "content": r.get("content", ""),
                "file_path": r.get("file_path", ""),
                "score": r.get("score", 0.0),
                "chunk_id": r.get("id", ""),
            }
            for r in results
        ]

        budget = TokenBudget(
            max_entity_tokens=param.max_entity_tokens,
            max_relation_tokens=param.max_relation_tokens,
            max_total_tokens=param.max_total_tokens,
        )
        chunks = budget.truncate_chunks(chunks)

        return self._context_builder.build(
            entities=[],
            relationships=[],
            chunks=chunks,
            is_kg_mode=False,
            include_references=param.include_references,
        )

    # ── Local mode (entity-centric) ──────────────────────────────

    async def _local_retrieve(
        self,
        param: QueryParam,
        hl_kw: list[str],
        ll_kw: list[str],
    ) -> QueryContext:
        """Entity-centric: search entities by LL keywords → find related edges → chunks."""
        # Search entities by low-level keywords
        entity_query = " ".join(ll_kw) if ll_kw else param.query
        entity_results = await self._vector.query(
            entity_query,
            top_k=param.top_k,
        )

        # Collect entity IDs and find related edges/chunks
        entities, relationships, chunks = await self._expand_from_entities(
            entity_results, param
        )

        return self._finalize_context(param, entities, relationships, chunks, is_kg=True)

    # ── Global mode (relation-centric) ───────────────────────────

    async def _global_retrieve(
        self,
        param: QueryParam,
        hl_kw: list[str],
        ll_kw: list[str],
    ) -> QueryContext:
        """Relation-centric: search relationships by HL keywords → find entities → chunks."""
        rel_query = " ".join(hl_kw) if hl_kw else param.query
        rel_results = await self._vector.query(
            rel_query,
            top_k=param.top_k,
        )

        entities, relationships, chunks = await self._expand_from_relations(
            rel_results, param
        )

        return self._finalize_context(param, entities, relationships, chunks, is_kg=True)

    # ── Hybrid mode ──────────────────────────────────────────────

    async def _hybrid_retrieve(
        self,
        param: QueryParam,
        hl_kw: list[str],
        ll_kw: list[str],
    ) -> QueryContext:
        """Combine local + global retrieval with round-robin merging."""
        local_ctx = await self._local_retrieve(param, hl_kw, ll_kw)
        global_ctx = await self._global_retrieve(param, hl_kw, ll_kw)

        # Round-robin merge and deduplicate
        entities = self._merge_dedup_entities(local_ctx.entities, global_ctx.entities)
        relationships = self._merge_dedup_relations(local_ctx.relationships, global_ctx.relationships)
        chunks = self._merge_dedup_chunks(local_ctx.chunks, global_ctx.chunks)

        return self._finalize_context(param, entities, relationships, chunks, is_kg=True)

    # ── Mix mode (recommended) ───────────────────────────────────

    async def _mix_retrieve(
        self,
        param: QueryParam,
        hl_kw: list[str],
        ll_kw: list[str],
    ) -> QueryContext:
        """KG retrieval (hybrid) + naive vector retrieval, merged."""
        hybrid_ctx = await self._hybrid_retrieve(param, hl_kw, ll_kw)
        naive_ctx = await self._naive_retrieve(param)

        entities = hybrid_ctx.entities
        relationships = hybrid_ctx.relationships
        chunks = self._merge_dedup_chunks(hybrid_ctx.chunks, naive_ctx.chunks)

        return self._finalize_context(param, entities, relationships, chunks, is_kg=True)

    # ── KG expansion helpers ─────────────────────────────────────

    async def _expand_from_entities(
        self,
        entity_results: list[dict[str, Any]],
        param: QueryParam,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """From entity search results, find related edges and chunks."""
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        chunk_ids: set[str] = set()

        for result in entity_results:
            entity_name = result.get("id", result.get("entity_name", ""))
            if not entity_name:
                continue

            # Get full entity data from graph
            node = await self._graph.get_node(entity_name)
            if node:
                entities.append(node)
                # Extract source_ids for chunk lookup
                source_ids = node.get("source_id", "")
                for sid in source_ids.split("<SEP>"):
                    sid = sid.strip()
                    if sid:
                        chunk_ids.add(sid)

            # Get connected edges
            edges = await self._graph.get_node_edges(entity_name)
            for src, tgt in edges:
                edge = await self._graph.get_edge(src, tgt)
                if edge:
                    relationships.append(edge)
                    source_ids = edge.get("source_id", "")
                    for sid in source_ids.split("<SEP>"):
                        sid = sid.strip()
                        if sid:
                            chunk_ids.add(sid)

        # Fetch chunks by IDs
        chunks = await self._fetch_chunks(list(chunk_ids), param.chunk_top_k)
        return entities, relationships, chunks

    async def _expand_from_relations(
        self,
        rel_results: list[dict[str, Any]],
        param: QueryParam,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """From relationship search results, find entities and chunks."""
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        chunk_ids: set[str] = set()
        seen_entities: set[str] = set()

        for result in rel_results:
            src = result.get("source_entity", result.get("src_id", ""))
            tgt = result.get("target_entity", result.get("tgt_id", ""))

            if src and tgt:
                relationships.append(result)
                source_ids = result.get("source_id", "")
                for sid in source_ids.split("<SEP>"):
                    sid = sid.strip()
                    if sid:
                        chunk_ids.add(sid)

                # Get connected entities
                for eid in [src, tgt]:
                    if eid not in seen_entities:
                        seen_entities.add(eid)
                        node = await self._graph.get_node(eid)
                        if node:
                            entities.append(node)

        chunks = await self._fetch_chunks(list(chunk_ids), param.chunk_top_k)
        return entities, relationships, chunks

    async def _fetch_chunks(
        self, chunk_ids: list[str], limit: int
    ) -> list[dict[str, Any]]:
        """Fetch chunk records by IDs."""
        if not chunk_ids:
            return []

        raw = await self._kv.get_by_ids(chunk_ids[:limit])
        return [
            {
                "content": r.get("content", ""),
                "file_path": r.get("file_path", ""),
                "chunk_id": r.get("id", ""),
            }
            for r in raw
            if r is not None
        ]

    # ── Finalize and budget ──────────────────────────────────────

    def _finalize_context(
        self,
        param: QueryParam,
        entities: list[dict],
        relationships: list[dict],
        chunks: list[dict],
        is_kg: bool,
    ) -> QueryContext:
        """Apply token budget and build context."""
        budget = TokenBudget(
            max_entity_tokens=param.max_entity_tokens,
            max_relation_tokens=param.max_relation_tokens,
            max_total_tokens=param.max_total_tokens,
        )

        entities = budget.truncate_entities(entities)
        relationships = budget.truncate_relations(relationships)
        chunks = budget.truncate_chunks(chunks)

        return self._context_builder.build(
            entities=entities,
            relationships=relationships,
            chunks=chunks,
            is_kg_mode=is_kg,
            include_references=param.include_references,
        )

    # ── Dedup/merge helpers ──────────────────────────────────────

    @staticmethod
    def _merge_dedup_entities(
        a: list[dict], b: list[dict]
    ) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for e in a + b:
            name = e.get("entity_name", e.get("id", ""))
            if name and name not in seen:
                seen.add(name)
                result.append(e)
        return result

    @staticmethod
    def _merge_dedup_relations(
        a: list[dict], b: list[dict]
    ) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for r in a + b:
            key = (
                f"{r.get('source_entity', r.get('src_id', ''))}|"
                f"{r.get('target_entity', r.get('tgt_id', ''))}"
            )
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result

    @staticmethod
    def _merge_dedup_chunks(
        a: list[dict], b: list[dict]
    ) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for c in a + b:
            cid = c.get("chunk_id", c.get("id", ""))
            if cid and cid not in seen:
                seen.add(cid)
                result.append(c)
        return result

    # ── Reranking ────────────────────────────────────────────────

    async def _apply_rerank(
        self, param: QueryParam, ctx: QueryContext
    ) -> QueryContext:
        """Apply reranker to chunks and reorder."""
        if not self._reranker or not ctx.chunks:
            return ctx

        docs = [c.get("content", "") for c in ctx.chunks]
        rerank_results = await self._reranker.rerank(
            param.query, docs, top_n=len(docs)
        )

        if not rerank_results:
            return ctx

        # Reorder chunks by rerank score
        reordered: list[dict] = []
        for rr in rerank_results:
            if rr.index < len(ctx.chunks):
                chunk = dict(ctx.chunks[rr.index])
                chunk["rerank_score"] = rr.score
                reordered.append(chunk)

        ctx.chunks = reordered
        return ctx

    # ── Response generation ──────────────────────────────────────

    def _build_response_prompt(
        self, param: QueryParam, ctx: QueryContext
    ) -> str:
        """Build the full response prompt with context."""
        context_str = self._context_builder.format_context(ctx)

        if ctx.is_kg_mode:
            template = PROMPTS["rag_response"]
        else:
            template = PROMPTS["naive_rag_response"]

        user_prompt = param.user_prompt or "None"
        return template.format(
            response_type=param.response_type,
            user_prompt=user_prompt,
            context_data=context_str,
            content_data=context_str,
        )

    def _build_conversation_messages(
        self, param: QueryParam, system_prompt: str = ""
    ) -> list[Message]:
        """Build message list from conversation history + query."""
        messages: list[Message] = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        for turn in param.conversation_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                messages.append(Message(role=role, content=content))

        messages.append(Message(role="user", content=param.query))
        return messages

    async def _generate(self, param: QueryParam, prompt: str) -> str:
        """Generate a complete response."""
        messages = self._build_conversation_messages(param, system_prompt=prompt)
        output = await self._llm.achat(messages)
        return output.text

    async def _stream_generate(
        self, param: QueryParam, prompt: str
    ) -> AsyncIterator[str]:
        """Stream a response chunk by chunk."""
        messages = self._build_conversation_messages(param, system_prompt=prompt)
        async for chunk in self._llm.achat_stream(messages):
            if chunk.text:
                yield chunk.text
