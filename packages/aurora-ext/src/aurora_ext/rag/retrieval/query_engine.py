"""Query engine — 6 retrieval modes combining KG + vector search.

Migrated from LightRAG ``operate.py`` query functions:
  - ``kg_query()``  (local/global/hybrid/mix)
  - ``naive_query()`` (vector-only)
  - bypass mode (direct LLM)

Query modes (per LightRAG paper arXiv:2410.05779):

  **naive** — Pure vector similarity search on document chunks.
    No knowledge-graph involvement.  Fast but misses relational knowledge.

  **local** — Entity-centric retrieval driven by *low-level* keywords.
    Searches for specific entities in the KG, expands to their neighbours
    and connected chunks.  Best for queries about concrete things.

  **global** — Relation-centric retrieval driven by *high-level* keywords.
    Searches for abstract relationships in the KG, collects connected
    entities and chunks.  Best for thematic / conceptual queries.

  **hybrid** — Combines local + global with deduplication.
    Runs both retrievals (in parallel) and merges results.

  **mix** — (Recommended) KG hybrid retrieval + naive vector retrieval.
    Combines structured knowledge with raw chunk similarity.
    Pairs well with a reranker.

  **bypass** — Skip all retrieval; pass the query straight to the LLM.
    Useful for chit-chat or when context is already supplied externally.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

from aurora_core.model.base import BaseLLM
from aurora_core.rag.utils.embedding import EmbeddingFunc
from aurora_core.schema.message import Message
from aurora_ext.rag.extraction.prompts import PROMPTS
from aurora_ext.rag.retrieval.citation_tracker import (
    Citation,
    CitationTracker,
    QueryResultWithCitations,
    distance_to_score,
)
from aurora_ext.rag.retrieval.context_builder import ContextBuilder, QueryContext
from aurora_ext.rag.retrieval.keyword_extractor import KeywordExtractor
from aurora_ext.rag.retrieval.reranker import RerankerBase
from aurora_ext.rag.retrieval.token_budget import TokenBudget
from aurora_ext.rag.storage.base import BaseGraphStorage, BaseKVStorage, BaseVectorStorage
from aurora_ext.rag.utils.token_tracker import TokenTracker

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

    All 18 parameters as documented in the migration plan, plus
    Aurora-specific tuning knobs.
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
    max_chunk_tokens: int = 8000
    token_tracker: Optional[TokenTracker] = None
    hl_keywords: list[str] = field(default_factory=list)
    ll_keywords: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    user_prompt: Optional[str] = None
    enable_rerank: bool = False
    include_references: bool = True
    include_chunk_content: bool = False
    stream: bool = False
    related_chunk_number: int = 5
    kg_chunk_pick_method: str = "VECTOR"
    max_graph_nodes: int = 1000


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

        # Apply reranking if enabled (mix mode enables by default when reranker available)
        should_rerank = param.enable_rerank or (mode == QueryMode.MIX and self._reranker)
        if should_rerank and self._reranker and ctx.chunks:
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

    async def query_with_citations(self, param: QueryParam) -> QueryResultWithCitations:
        """Execute a query and return the result with structured citations.

        Wraps :meth: and converts the retrieved chunks into
        :class: objects, sorted by score and deduplicated.
        """
        result = await self.query(param)
        citations = self._build_citations(result)
        return QueryResultWithCitations(
            answer=result.response,
            citations=tuple(citations),
            metadata={
                "mode": param.mode.value,
                "hl_keywords": result.hl_keywords,
                "ll_keywords": result.ll_keywords,
                "entity_count": len(result.entities),
                "relationship_count": len(result.relationships),
            },
        )

    @staticmethod
    def _build_citations(result: QueryResult) -> list[Citation]:
        """Convert chunks from a QueryResult into Citation objects."""
        if not result.chunks:
            return []
        raw = []
        for c in result.chunks:
            score = c.get("rerank_score") or c.get("score", 0.0)
            raw.append({
                "content": c.get("content", ""),
                "chunk_id": c.get("chunk_id", c.get("id", "")),
                "file_path": c.get("file_path", ""),
                "page_number": c.get("page_number"),
                "score": float(score) if score else 0.0,
                "start_pos": c.get("start_pos"),
                "end_pos": c.get("end_pos"),
            })
        return CitationTracker.build(raw)

    # ── Bypass mode ──────────────────────────────────────────────

    async def _bypass_query(self, param: QueryParam) -> QueryResult:
        """Direct LLM pass-through — no retrieval, no KG.

        Bypasses both the knowledge graph and vector search entirely.
        The query is forwarded directly to the LLM along with any
        conversation history.  Useful for:
          - Chit-chat / greetings
          - Queries where context is supplied externally
          - Debugging LLM behavior in isolation
        """
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
            max_chunk_tokens=param.max_chunk_tokens,
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
        """Entity-centric: search entities by LL keywords → find related edges → chunks.

        Uses a dual-path approach for robust entity discovery:
          1. **Vector search** on entity embeddings using LL keywords
          2. **Graph label search** (fuzzy substring) on entity names

        Results are merged, then expanded via BFS to include neighbours
        and their connecting edges.
        """
        entity_query = " ".join(ll_kw) if ll_kw else param.query

        # Path 1: Vector similarity search on entity embeddings
        vector_results = await self._vector.query(
            entity_query,
            top_k=param.top_k,
        )

        # Path 2: Graph label fuzzy search (fast, exact-ish match)
        label_matches: list[str] = []
        try:
            label_matches = await self._graph.search_labels(
                entity_query, limit=param.top_k
            )
        except Exception as exc:
            logger.debug("Graph label search unavailable: %s", exc)

        # Merge entity names from both paths, preserving order
        seen_names: set[str] = set()
        merged_entity_ids: list[str] = []

        for r in vector_results:
            name = r.get("id", r.get("entity_name", ""))
            if name and name not in seen_names:
                seen_names.add(name)
                merged_entity_ids.append(name)

        for label in label_matches:
            if label not in seen_names:
                seen_names.add(label)
                merged_entity_ids.append(label)

        # Build synthetic result dicts for graph-label-only matches
        entity_results: list[dict[str, Any]] = []
        for r in vector_results:
            entity_results.append(r)

        vector_ids = {
            r.get("id", r.get("entity_name", "")) for r in vector_results
        }
        for label in label_matches:
            if label not in vector_ids:
                entity_results.append({"id": label, "entity_name": label})

        # Expand from entities → edges → chunks (with neighbour BFS)
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
        """Relation-centric: search relationships by HL keywords → find entities → chunks.

        Prioritises high-level conceptual matches:
          1. Vector search on relationship embeddings using HL keywords
          2. Sort results by relationship weight (most significant first)
          3. Collect connected entities and source chunks

        Best for thematic / conceptual queries where the answer spans
        multiple entities connected by abstract relationships.
        """
        rel_query = " ".join(hl_kw) if hl_kw else param.query
        rel_results = await self._vector.query(
            rel_query,
            top_k=param.top_k,
        )

        # Sort by weight (descending) to prioritise significant relationships
        rel_results.sort(
            key=lambda r: float(r.get("weight", 0.0)),
            reverse=True,
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
        """Combine local + global retrieval with parallel execution.

        Runs both retrieval paths concurrently via ``asyncio.gather``
        to halve wall-clock latency, then merges and deduplicates.
        """
        local_ctx, global_ctx = await asyncio.gather(
            self._local_retrieve(param, hl_kw, ll_kw),
            self._global_retrieve(param, hl_kw, ll_kw),
        )

        # Merge and deduplicate across both paths
        entities = self._merge_dedup_entities(local_ctx.entities, global_ctx.entities)
        relationships = self._merge_dedup_relations(
            local_ctx.relationships, global_ctx.relationships
        )
        chunks = self._merge_dedup_chunks(local_ctx.chunks, global_ctx.chunks)

        return self._finalize_context(param, entities, relationships, chunks, is_kg=True)

    # ── Mix mode (recommended) ───────────────────────────────────

    async def _mix_retrieve(
        self,
        param: QueryParam,
        hl_kw: list[str],
        ll_kw: list[str],
    ) -> QueryContext:
        """KG retrieval (hybrid) + naive vector retrieval, merged.

        Runs KG hybrid retrieval and naive vector search concurrently.
        KG entities and relationships are preserved; chunks from both
        paths are merged with deduplication.

        Pairs well with ``enable_rerank=True`` for optimal results.
        """
        hybrid_ctx, naive_ctx = await asyncio.gather(
            self._hybrid_retrieve(param, hl_kw, ll_kw),
            self._naive_retrieve(param),
        )

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
        """From entity search results, find related edges, neighbours, and chunks.

        Expansion strategy (BFS, depth-1):
          1. For each matched entity, fetch its full node data from the graph
          2. Collect all edges connected to the entity
          3. For each edge, discover the *other* endpoint (neighbour)
          4. Fetch neighbour node data (up to ``max_graph_nodes``)
          5. Aggregate chunk IDs from entities + edges
          6. Batch-fetch chunk content
        """
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        chunk_ids: set[str] = set()
        seen_entities: set[str] = set()
        node_count = 0

        # Phase 1: Resolve seed entities
        seed_names: list[str] = []
        for result in entity_results:
            if node_count >= param.max_graph_nodes:
                break
            entity_name = result.get("id", result.get("entity_name", ""))
            if not entity_name or entity_name in seen_entities:
                continue

            seen_entities.add(entity_name)
            node = await self._graph.get_node(entity_name)
            if node:
                entities.append(node)
                node_count += 1
                seed_names.append(entity_name)
                source_ids = node.get("source_id", "")
                related_ids = self._pick_chunk_ids(
                    source_ids, param.related_chunk_number, param.kg_chunk_pick_method
                )
                chunk_ids.update(related_ids)

        # Phase 2: Expand edges and discover neighbours (BFS depth-1)
        seen_edges: set[str] = set()
        for entity_name in seed_names:
            if node_count >= param.max_graph_nodes:
                break

            edges = await self._graph.get_node_edges(entity_name)
            for src, tgt in edges:
                edge_key = f"{src}|{tgt}"
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                edge = await self._graph.get_edge(src, tgt)
                if edge:
                    relationships.append(edge)
                    source_ids = edge.get("source_id", "")
                    related_ids = self._pick_chunk_ids(
                        source_ids, param.related_chunk_number, param.kg_chunk_pick_method
                    )
                    chunk_ids.update(related_ids)

                # Discover neighbour (the "other" side of the edge)
                neighbour = tgt if src == entity_name else src
                if neighbour and neighbour not in seen_entities:
                    if node_count >= param.max_graph_nodes:
                        break
                    seen_entities.add(neighbour)
                    neighbour_node = await self._graph.get_node(neighbour)
                    if neighbour_node:
                        entities.append(neighbour_node)
                        node_count += 1
                        source_ids = neighbour_node.get("source_id", "")
                        related_ids = self._pick_chunk_ids(
                            source_ids, param.related_chunk_number, param.kg_chunk_pick_method
                        )
                        chunk_ids.update(related_ids)

        # Phase 3: Batch-fetch chunk content
        chunks = await self._fetch_chunks(list(chunk_ids), param.chunk_top_k)
        return entities, relationships, chunks

    async def _expand_from_relations(
        self,
        rel_results: list[dict[str, Any]],
        param: QueryParam,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """From relationship search results, find entities and chunks.

        Expansion strategy:
          1. For each matched relationship, collect the edge data
          2. Resolve both endpoint entities from the graph
          3. Aggregate chunk IDs from relationships + entities
          4. Batch-fetch chunk content
        """
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        chunk_ids: set[str] = set()
        seen_entities: set[str] = set()
        seen_edges: set[str] = set()
        node_count = 0

        for result in rel_results:
            src = result.get("source_entity", result.get("src_id", ""))
            tgt = result.get("target_entity", result.get("tgt_id", ""))

            if not (src and tgt):
                continue

            edge_key = f"{src}|{tgt}"
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            relationships.append(result)
            source_ids = result.get("source_id", "")
            related_ids = self._pick_chunk_ids(
                source_ids, param.related_chunk_number, param.kg_chunk_pick_method
            )
            chunk_ids.update(related_ids)

            # Resolve both endpoint entities
            for eid in [src, tgt]:
                if eid in seen_entities:
                    continue
                if node_count >= param.max_graph_nodes:
                    break
                seen_entities.add(eid)
                node = await self._graph.get_node(eid)
                if node:
                    entities.append(node)
                    node_count += 1
                    # Also collect entity source chunks
                    node_source_ids = node.get("source_id", "")
                    node_chunk_ids = self._pick_chunk_ids(
                        node_source_ids,
                        param.related_chunk_number,
                        param.kg_chunk_pick_method,
                    )
                    chunk_ids.update(node_chunk_ids)

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
                "page_number": r.get("page_number"),
                "start_pos": r.get("start_pos"),
                "end_pos": r.get("end_pos"),
                "weight": float(r.get("weight", 0.0)),
            }
            for r in raw
            if r is not None
        ]

    @staticmethod
    def _pick_chunk_ids(
        source_ids: str,
        related_chunk_number: int,
        method: str = "VECTOR",
    ) -> set[str]:
        """Select chunk IDs from a source-ID string based on the pick method.

        Parameters
        ----------
        source_ids:
            ``<SEP>``-delimited chunk ID string from a graph node/edge.
        related_chunk_number:
            Maximum number of chunk IDs to return.
        method:
            ``"VECTOR"`` keeps the *last* N IDs (most recently appended,
            which are the ones most similar to the embedding query).
            ``"WEIGHT"`` keeps the *first* N IDs (which in a weight-sorted
            list correspond to the highest-weight entities/relations).
        """
        if not source_ids:
            return set()

        ids = [s.strip() for s in source_ids.split("<SEP>") if s.strip()]
        if not ids:
            return set()

        if method.upper() == "WEIGHT":
            # WEIGHT mode: assume IDs are ordered by entity/edge weight
            # (highest first), so take the first N.
            selected = ids[:related_chunk_number]
        else:
            # VECTOR mode (default): take the last N IDs (newest / most
            # relevant to the embedding search that produced them).
            selected = ids[-related_chunk_number:]

        return set(selected)

    # ── Finalize and budget ──────────────────────────────────────

    def _finalize_context(
        self,
        param: QueryParam,
        entities: list[dict],
        relationships: list[dict],
        chunks: list[dict],
        is_kg: bool,
    ) -> QueryContext:
        """Apply token budget and build context.

        When a ``TokenTracker`` is attached to the query parameters,
        the tracker's priority-based truncation is used instead of
        the simple per-category truncation.
        """
        if param.token_tracker is not None:
            # Use the fine-grained tracker with priority ordering
            from aurora_ext.rag.utils.token_tracker import TokenBudget as TrackerBudget

            tracker_budget = TrackerBudget(
                max_entity_tokens=param.max_entity_tokens,
                max_relation_tokens=param.max_relation_tokens,
                max_total_tokens=param.max_total_tokens,
                max_chunk_tokens=param.max_chunk_tokens,
            )
            param.token_tracker.budget = tracker_budget
            entities, relationships, chunks = param.token_tracker.truncate_to_budget(
                entities, relationships, chunks
            )
        else:
            # Legacy per-category truncation
            budget = TokenBudget(
                max_entity_tokens=param.max_entity_tokens,
                max_relation_tokens=param.max_relation_tokens,
                max_total_tokens=param.max_total_tokens,
                max_chunk_tokens=param.max_chunk_tokens,
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
