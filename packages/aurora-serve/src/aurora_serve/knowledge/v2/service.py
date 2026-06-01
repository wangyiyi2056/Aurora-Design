"""KnowledgeV2Service — integration layer for the RAG knowledge base.

Wires together storage backends, the retrieval engine, the pipeline manager,
and graph operations into a single service consumed by all V2 route files.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile

from aurora_core.component import BaseService
from aurora_core.model.base import BaseLLM
from aurora_core.model.registry import ModelRegistry
from aurora_core.rag.namespace import NameSpace
from aurora_core.rag.utils.embedding import EmbeddingConfig, EmbeddingFunc
from aurora_core.rag.utils.hashing import compute_args_hash, compute_mdhash_id
from aurora_ext.rag.pipeline.status import PipelineCancelledError, PipelineManager
from aurora_ext.rag.retrieval.query_engine import QueryEngine, QueryMode, QueryParam
from aurora_ext.rag.utils.token_tracker import TokenBudget as TrackerBudget
from aurora_ext.rag.utils.token_tracker import TokenTracker
from aurora_ext.rag.storage.base import (
    BaseDocStatusStorage,
    BaseGraphStorage,
    BaseKVStorage,
    BaseVectorStorage,
    DocStatus,
    DocStatusInfo,
)

from aurora_serve.knowledge.v2.schemas import (
    DocStatusEnum,
    InsertResponse,
    InsertStatusEnum,
    PipelineStatusResponse,
    QueryMode as SchemaQueryMode,
    ScanResponse,
    ScanStatusEnum,
    StatusCountsResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class _BatchRunContext:
    """Shared state for a concurrent pipeline batch run."""
    kb_name: str
    semaphore: asyncio.Semaphore
    graph_lock: asyncio.Lock
    extractor: Any  # EntityRelationExtractor
    chunker: Any  # FixedTokenChunker
    analyzer: Any | None = None  # MultimodalAnalyzer (optional)


def _doc_status_to_dict(info: DocStatusInfo) -> dict[str, Any]:
    """Convert a DocStatusInfo dataclass to a serialisable dict."""
    return {
        "id": info.id,
        "content_summary": info.content_summary,
        "content_length": info.content_length,
        "status": info.status.value if isinstance(info.status, DocStatus) else str(info.status),
        "created_at": info.created_at,
        "updated_at": info.updated_at,
        "track_id": info.track_id,
        "chunks_count": info.chunks_count,
        "error_msg": info.error_msg,
        "metadata": info.metadata,
        "file_path": info.file_path,
        "kb_name": info.kb_name,
        "content_hash": info.content_hash,
        "duplicate_kind": info.duplicate_kind,
        "basename": info.basename,
    }


def _schema_mode_to_engine(mode: SchemaQueryMode | str) -> QueryMode:
    """Map a schema QueryMode enum (or string) to the engine's QueryMode."""
    mapping = {
        "local": QueryMode.LOCAL,
        "global": QueryMode.GLOBAL,
        "hybrid": QueryMode.HYBRID,
        "naive": QueryMode.NAIVE,
        "mix": QueryMode.MIX,
        "bypass": QueryMode.BYPASS,
    }
    key = mode.value if hasattr(mode, "value") else str(mode)
    return mapping.get(key, QueryMode.MIX)


def _schema_status_to_core(status: DocStatusEnum | None) -> DocStatus | None:
    """Convert a schema DocStatusEnum to the core DocStatus enum."""
    if status is None:
        return None
    mapping = {
        DocStatusEnum.PENDING: DocStatus.PENDING,
        DocStatusEnum.PARSING: DocStatus.PARSING,
        DocStatusEnum.ANALYZING: DocStatus.ANALYZING,
        DocStatusEnum.PREPROCESSED: DocStatus.PREPROCESSED,
        DocStatusEnum.PROCESSING: DocStatus.PROCESSING,
        DocStatusEnum.PROCESSED: DocStatus.PROCESSED,
        DocStatusEnum.FAILED: DocStatus.FAILED,
    }
    return mapping.get(status)


class KnowledgeV2Service(BaseService):
    """Integration service for the Knowledge V2 API layer.

    Wraps all Phase 1-4 components (storage, retrieval, pipeline, graph)
    behind a single facade consumed by every V2 route handler.
    """

    name = "knowledge_v2_service"

    # Concurrency configuration (mirrors LightRAG defaults)
    MAX_PARSE_WORKERS: int = 4
    MAX_ANALYZE_WORKERS: int = 2
    MAX_PROCESS_WORKERS: int = 2
    QUEUE_SIZE: int = 100

    # Hold strong references to background tasks to prevent GC.
    # asyncio.create_task() returns a task the event loop only weakly
    # references — without this set the task is garbage-collected before
    # it ever runs, silently killing the pipeline.
    _active_tasks: set[asyncio.Task] = set()

    def __init__(
        self,
        *,
        llm: BaseLLM | None = None,
        embedding_func: EmbeddingFunc | None = None,
        kv_storage: BaseKVStorage,
        vector_storage: BaseVectorStorage,
        graph_storage: BaseGraphStorage,
        doc_status_storage: BaseDocStatusStorage,
        model_registry: ModelRegistry | None = None,
        working_dir: str = "",
        input_dir: str = "",
        reranker: Any | None = None,
        role_configs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._llm = llm
        self._embedding_func = embedding_func
        self._kv = kv_storage
        self._vector = vector_storage
        self._graph = graph_storage
        self._doc_status = doc_status_storage
        self._registry = model_registry
        self._working_dir = working_dir or os.getenv(
            "AURORA_KNOWLEDGE_DIR", "./rag_storage"
        )
        self._input_dir = input_dir or os.getenv(
            "AURORA_INPUT_DIR", "./rag_input"
        )

        # Initialise the query engine (Phase 4) - only if we have LLM + embeddings
        self._query_engine = None
        if llm and embedding_func:
            self._query_engine = QueryEngine(
                llm=llm,
                embedding_func=embedding_func,
                kv_storage=kv_storage,
                vector_storage=vector_storage,
                graph_storage=graph_storage,
                reranker=reranker,
            )

        # Initialise the pipeline manager (Phase 2)
        self._pipeline = PipelineManager(doc_status_storage=doc_status_storage)

        # Per-KB token trackers for usage statistics
        self._token_trackers: dict[str, TokenTracker] = {}

        # Role registry for per-role LLM bindings (VLM, extraction, etc.)
        self._role_registry = None
        self._role_configs = role_configs
        if model_registry is not None:
            from aurora_core.model.roles import LLMRoleRegistry
            self._role_registry = LLMRoleRegistry(model_registry)
            if role_configs:
                self._apply_role_configs(role_configs)

    def _spawn_task(self, coro) -> asyncio.Task:
        """Create a background task and keep it alive until it finishes."""
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)

        def _on_done(t: asyncio.Task) -> None:
            self._active_tasks.discard(t)
            if t.cancelled():
                logger.warning("Background task was cancelled")
            elif t.exception():
                logger.error(
                    "Background task failed with exception: %s",
                    t.exception(),
                    exc_info=t.exception(),
                )
            else:
                logger.info("Background task completed successfully")

        task.add_done_callback(_on_done)
        logger.info("Spawned background pipeline task: %s", task.get_name())
        return task

    def _apply_role_configs(
        self, role_configs: dict[str, dict[str, Any]]
    ) -> None:
        """Apply TOML + env-var role configs to the internal role registry.

        Called during synchronous ``__init__``. When the caller is inside an
        async context (e.g. FastAPI lifespan), the async apply is scheduled
        as a task that completes before any request is served.
        """
        if self._role_registry is None:
            return

        from aurora_core.llm.role_config import LLMRoleConfigManager

        manager = LLMRoleConfigManager(role_configs)
        configured = manager.configured_roles()
        if not configured:
            logger.debug("No LLM role configs to apply")
            return

        async def _apply() -> None:
            await manager.apply_to(self._role_registry)

        try:
            loop = asyncio.get_running_loop()
            # Schedule but keep a reference so the task is not GC'd.
            task = loop.create_task(_apply(), name="apply-role-configs")
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)
        except RuntimeError:
            # No running loop — run synchronously in a throwaway loop.
            asyncio.run(_apply())

        logger.info(
            "Scheduled %d LLM role config(s): %s",
            len(configured),
            ", ".join(r.value for r in configured),
        )

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_registry(
        cls,
        registry: ModelRegistry,
        *,
        kv_storage: BaseKVStorage,
        vector_storage: BaseVectorStorage,
        graph_storage: BaseGraphStorage,
        doc_status_storage: BaseDocStatusStorage,
        working_dir: str = "",
        input_dir: str = "",
        reranker: Any | None = None,
        role_configs: dict[str, dict[str, Any]] | None = None,
    ) -> "KnowledgeV2Service":
        """Build a KnowledgeV2Service from a ModelRegistry + storage backends.

        This is the primary entry point used during application bootstrap.
        """
        try:
            llm = registry.get_llm()
        except RuntimeError:
            llm = None
            logger.warning(
                "⚠️  Knowledge V2 Service: No LLM available. "
                "Document ingestion and querying will not work. "
                "Set OPENAI_API_KEY or configure api_key in configs/aurora.toml."
            )

        try:
            embeddings = registry.get_embeddings()

            async def _embed_callable(texts: list[str]) -> list[list[float]]:
                return await embeddings.aembed(texts)

            embedding_func = EmbeddingFunc(
                embed_func=_embed_callable,
                config=EmbeddingConfig(),
            )
        except RuntimeError:
            embedding_func = None
            logger.warning(
                "⚠️  Knowledge V2 Service: No embedding model available. "
                "Vector search will not work. "
                "Set OPENAI_API_KEY or configure embeddings in configs/aurora.toml."
            )

        return cls(
            llm=llm,
            embedding_func=embedding_func,
            kv_storage=kv_storage,
            vector_storage=vector_storage,
            graph_storage=graph_storage,
            doc_status_storage=doc_status_storage,
            model_registry=registry,
            working_dir=working_dir,
            input_dir=input_dir,
            reranker=reranker,
            role_configs=role_configs,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def _ns(self, kb_name: str, key: str) -> str:
        """Namespace a storage key by knowledge base name."""
        return f"{kb_name}:{key}"

    def _try_rebuild_llm(self) -> None:
        """Lazily initialise the LLM from the registry.

        Called at the start of the ingestion pipeline and query methods so
        that a user can bind a chat model (CLI agent / BYOK API) *after*
        the server has started.
        """
        if self._llm is not None:
            return
        if self._registry is None:
            return
        try:
            self._llm = self._registry.get_llm()
            logger.info("✅ LLM loaded from registry: %s", type(self._llm).__name__)
        except RuntimeError:
            pass

    def _try_rebuild_embedding(self) -> None:
        """Lazily initialise the embedding function from the registry.

        Called at the start of the ingestion pipeline so that a user can
        configure an embedding model *after* the server has started.
        """
        if self._embedding_func is not None:
            return
        if self._registry is None:
            return
        try:
            embeddings = self._registry.get_embeddings()

            async def _embed_callable(texts: list[str]) -> list[list[float]]:
                return await embeddings.aembed(texts)

            self._embedding_func = EmbeddingFunc(
                embed_func=_embed_callable,
                config=EmbeddingConfig(),
            )
            logger.info("✅ Embedding model loaded and ready")
        except RuntimeError:
            pass

    def _try_rebuild_query_engine(self) -> None:
        """Lazily initialise the query engine once both LLM and embeddings are available."""
        if self._query_engine is not None:
            return
        # Ensure both LLM and embeddings are loaded before building
        self._try_rebuild_llm()
        self._try_rebuild_embedding()
        if self._llm is None or self._embedding_func is None:
            return
        self._query_engine = QueryEngine(
            llm=self._llm,
            embedding_func=self._embedding_func,
            kv_storage=self._kv,
            vector_storage=self._vector,
            graph_storage=self._graph,
            reranker=None,
        )
        logger.info("✅ Query engine initialised")

    def is_ready(self) -> dict[str, bool]:
        """Return readiness status for LLM and embedding."""
        self._try_rebuild_llm()
        self._try_rebuild_embedding()
        self._try_rebuild_query_engine()
        return {
            "llm": self._llm is not None,
            "embedding": self._embedding_func is not None,
            "query_engine": self._query_engine is not None,
        }

    # ── Ingestion Pipeline ──────────────────────────────────────────

    # ── Concurrent Pipeline (LightRAG-style cascading queues) ────────

    async def _process_pending_documents(
        self, kb_name: str, track_id: str
    ) -> None:
        """Execute the full ingestion pipeline for PENDING documents.

        Uses cascading async queues with worker pools for concurrent processing:

            q_parse  →  parse_workers × 4     (file I/O, fast)
                ↓                    ↓ (VLM hints present)
                ↓               q_analyze → analyze_workers × 2 (VLM analysis)
                ↓                    ↓
            q_process → process_workers × 2   (LLM extraction, semaphore-gated)
        """
        logger.info("🚀 Pipeline task started for kb=%s track_id=%s", kb_name, track_id)

        from aurora_ext.rag.chunker import FixedTokenChunker, ChunkParameters
        from aurora_ext.rag.extraction import EntityRelationExtractor

        # Check if pipeline is already busy
        if self._pipeline.is_busy:
            logger.info("Pipeline already busy, setting request_pending=True")
            await self._pipeline.set_request_pending(True)
            return

        # Get ALL PENDING docs for this KB (not filtered by track_id)
        # This allows the pipeline to batch docs from multiple uploads together
        pending_docs = await self._doc_status.get_docs_by_status(
            DocStatus.PENDING, kb_name=kb_name
        )
        logger.info("Found %d pending docs for kb=%s", len(pending_docs), kb_name)
        if not pending_docs:
            logger.warning("No pending docs found, pipeline task exiting early")
            return

        # Start pipeline IMMEDIATELY so the frontend sees busy=true
        await self._pipeline.start_job(
            f"Processing {len(pending_docs)} documents",
            total_docs=len(pending_docs),
        )
        logger.info("✅ Pipeline started, busy=True, total_docs=%d", len(pending_docs))

        try:
            # Guard: LLM is required for entity extraction
            self._try_rebuild_llm()
            if self._llm is None:
                error_msg = (
                    "Chat model (LLM) not configured. Please bind a chat model "
                    "in the Models page first (select a CLI agent or configure BYOK API)."
                )
                logger.error(error_msg)
                await self._pipeline.update_progress(f"ERROR: {error_msg}")
                for doc_info in pending_docs:
                    await self._doc_status.update_status(
                        doc_info.id, DocStatus.FAILED, error_msg=error_msg
                    )
                await self._pipeline.finish_job()
                return

            # Guard: Embedding model is required for vector storage
            self._try_rebuild_embedding()
            if self._embedding_func is None:
                error_msg = (
                    "Embedding model not configured. Please bind an embedding model "
                    "in the Models page (Embedding tab) first."
                )
                logger.error(error_msg)
                await self._pipeline.update_progress(f"ERROR: {error_msg}")
                for doc_info in pending_docs:
                    await self._doc_status.update_status(
                        doc_info.id, DocStatus.FAILED, error_msg=error_msg
                    )
                await self._pipeline.finish_job()
                return

            extractor = EntityRelationExtractor(self._llm)
            chunker = FixedTokenChunker(ChunkParameters(chunk_size=1200, chunk_overlap=100))

            # Initialise multimodal analyzer (optional — requires role registry)
            analyzer = None
            if self._role_registry is not None:
                from aurora_ext.rag.extraction.multimodal_analyzer import (
                    MultimodalAnalyzer,
                )
                analyzer = MultimodalAnalyzer(self._role_registry)

            # Build batch context
            ctx = _BatchRunContext(
                kb_name=kb_name,
                semaphore=asyncio.Semaphore(self.MAX_PROCESS_WORKERS),
                graph_lock=asyncio.Lock(),
                extractor=extractor,
                chunker=chunker,
                analyzer=analyzer,
            )

            # Create cascading queues (three-layer pipeline)
            q_parse: asyncio.Queue[DocStatusInfo | None] = asyncio.Queue(
                maxsize=self.QUEUE_SIZE
            )
            q_analyze: asyncio.Queue[tuple | None] = asyncio.Queue(
                maxsize=self.QUEUE_SIZE
            )
            q_process: asyncio.Queue[tuple | None] = asyncio.Queue(
                maxsize=self.QUEUE_SIZE
            )

            # Spawn parse workers (Layer 1 — file I/O, fast)
            parse_workers = [
                asyncio.create_task(
                    self._parse_worker(q_parse, q_analyze, q_process, ctx),
                    name=f"parse-worker-{i}",
                )
                for i in range(self.MAX_PARSE_WORKERS)
            ]

            # Spawn analyze workers (Layer 2 — VLM multimodal analysis)
            analyze_workers = [
                asyncio.create_task(
                    self._analyze_worker(q_analyze, q_process, ctx),
                    name=f"analyze-worker-{i}",
                )
                for i in range(self.MAX_ANALYZE_WORKERS)
            ]

            # Spawn process workers (Layer 3 — LLM extraction, semaphore-gated)
            process_workers = [
                asyncio.create_task(
                    self._process_worker(q_process, ctx),
                    name=f"process-worker-{i}",
                )
                for i in range(self.MAX_PROCESS_WORKERS)
            ]

            # Enqueue all pending docs for parsing
            for doc_info in pending_docs:
                await q_parse.put(doc_info)

            # Send sentinels to signal parse workers to stop
            for _ in range(self.MAX_PARSE_WORKERS):
                await q_parse.put(None)

            # Wait for all parse workers to finish
            await asyncio.gather(*parse_workers)

            # All parsing done — send sentinels to analyze workers
            for _ in range(self.MAX_ANALYZE_WORKERS):
                await q_analyze.put(None)

            # Wait for all analyze workers to finish
            await asyncio.gather(*analyze_workers)

            # All analysis done — send sentinels to process workers
            for _ in range(self.MAX_PROCESS_WORKERS):
                await q_process.put(None)

            # Wait for all process workers to finish
            await asyncio.gather(*process_workers)

            # Check if new documents were queued while we were processing
            if self._pipeline.status.request_pending:
                await self._pipeline.set_request_pending(False)
                logger.info("🔄 request_pending=True, checking for new documents")
                new_pending = await self._doc_status.get_docs_by_status(
                    DocStatus.PENDING, kb_name=kb_name
                )
                if new_pending:
                    logger.info("Found %d new pending docs, continuing pipeline", len(new_pending))
                    await self._pipeline.finish_job()
                    # Recurse for the next batch (avoids deeply nested state)
                    await self._process_pending_documents(kb_name, "batch")
                    return

        except PipelineCancelledError:
            logger.info("Pipeline cancelled by user")
            await self._pipeline.update_progress("Pipeline cancelled")
        except Exception as exc:
            logger.exception("Pipeline crashed unexpectedly")
            error_msg = f"Pipeline error: {str(exc)[:500]}"
            await self._pipeline.update_progress(f"ERROR: {error_msg}")
            remaining = await self._doc_status.get_docs_by_status(
                DocStatus.PENDING, kb_name=kb_name
            )
            for doc_info in remaining:
                await self._doc_status.update_status(
                    doc_info.id, DocStatus.FAILED, error_msg=error_msg
                )
        finally:
            await self._pipeline.finish_job()

    # ── Pipeline Workers ─────────────────────────────────────────────

    async def _parse_worker(
        self,
        q_parse: asyncio.Queue[DocStatusInfo | None],
        q_analyze: asyncio.Queue[tuple | None],
        q_process: asyncio.Queue[tuple | None],
        ctx: _BatchRunContext,
    ) -> None:
        """Layer 1: Parse files and route to analyze or process queue.

        Documents with VLM hints (``i``, ``t``, ``e``) are routed to
        ``q_analyze`` for multimodal analysis. All others go directly
        to ``q_process``.
        """
        from aurora_ext.rag.extraction.multimodal_analyzer import has_vlm_hints
        from aurora_ext.rag.parser.routing import parse_file

        while True:
            try:
                doc_info = await q_parse.get()
            except asyncio.CancelledError:
                return

            if doc_info is None:  # sentinel
                q_parse.task_done()
                return

            doc_id = doc_info.id
            file_path = doc_info.file_path
            kb_name = ctx.kb_name

            try:
                self._pipeline.check_cancellation()

                # Mark as PARSING with start time
                parse_start = time.time()
                file_size = 0
                if file_path and Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size

                await self._doc_status.update_status(
                    doc_id,
                    DocStatus.PARSING,
                    metadata={
                        "parse_start_time": parse_start,
                        "file_size": file_size,
                    },
                )
                await self._pipeline.update_progress(
                    f"Parsing {doc_info.content_summary[:50]}",
                    parsing_delta=1,
                )

                raw_text = ""
                if file_path and Path(file_path).exists():
                    parse_result = await parse_file(file_path)
                    raw_text = parse_result.text
                else:
                    stored = await self._kv.get_by_id(self._ns(kb_name, doc_id))
                    if stored:
                        raw_text = stored.get("content", "")

                if not raw_text.strip():
                    await self._doc_status.update_status(
                        doc_id, DocStatus.FAILED, error_msg="Empty document"
                    )
                    await self._pipeline.update_progress(
                        f"Skipped empty: {doc_info.content_summary[:50]}",
                        failed=1,
                        parsing_delta=-1,
                    )
                    continue  # finally block will call task_done()

                # Store full document in KV
                full_doc_key = self._ns(
                    kb_name, f"{NameSpace.KV_STORE_FULL_DOCS}:{doc_id}"
                )
                await self._kv.upsert({
                    full_doc_key: {
                        "content": raw_text,
                        "file_path": file_path,
                        "id": full_doc_key,
                    }
                })

                # Route to analyze queue (VLM hints) or directly to process queue
                parse_options = doc_info.metadata.get("parse_options", {})
                needs_vlm = (
                    has_vlm_hints(parse_options)
                    and ctx.analyzer is not None
                )

                if needs_vlm:
                    await q_analyze.put((doc_info, raw_text))
                    await self._pipeline.update_progress(
                        f"Parsed (→VLM) {doc_info.content_summary[:50]}",
                        parsing_delta=-1,
                    )
                else:
                    await q_process.put((doc_info, raw_text))
                    await self._pipeline.update_progress(
                        f"Parsed {doc_info.content_summary[:50]}",
                        parsing_delta=-1,
                    )

            except PipelineCancelledError:
                await self._doc_status.update_status(
                    doc_id, DocStatus.FAILED, error_msg="Pipeline cancelled"
                )
                await self._pipeline.update_progress(
                    "Pipeline cancelled", failed=1, parsing_delta=-1
                )
            except Exception as exc:
                logger.exception("Parse failed for doc %s", doc_id)
                await self._doc_status.update_status(
                    doc_id, DocStatus.FAILED, error_msg=str(exc)[:500]
                )
                await self._pipeline.update_progress(
                    f"Parse failed: {doc_info.content_summary[:50]}: {str(exc)[:100]}",
                    failed=1,
                    parsing_delta=-1,
                )
            finally:
                q_parse.task_done()

    async def _analyze_worker(
        self,
        q_analyze: asyncio.Queue[tuple | None],
        q_process: asyncio.Queue[tuple | None],
        ctx: _BatchRunContext,
    ) -> None:
        """Layer 2: Run VLM multimodal analysis on documents with hints.

        Documents with ``i`` / ``t`` / ``e`` filename hints are routed here
        after parsing. The analyzer inspects images, tables, and equations
        extracted from the document and stores the results in
        ``doc_status.metadata`` before forwarding to the process queue.
        """
        from aurora_ext.rag.extraction.multimodal_analyzer import get_enabled_modes

        while True:
            try:
                item = await q_analyze.get()
            except asyncio.CancelledError:
                return

            if item is None:  # sentinel
                q_analyze.task_done()
                return

            doc_info, raw_text = item
            doc_id = doc_info.id
            kb_name = ctx.kb_name

            try:
                self._pipeline.check_cancellation()

                # Mark as ANALYZING
                await self._doc_status.update_status(
                    doc_id, DocStatus.ANALYZING
                )
                await self._pipeline.update_progress(
                    f"Analysing (VLM) {doc_info.content_summary[:50]}",
                    analyzing_delta=1,
                )

                parse_options = doc_info.metadata.get("parse_options", {})
                enabled_modes = get_enabled_modes(parse_options)

                # Collect multimodal elements from the parse result metadata.
                # The parser may have extracted images/tables/equations as
                # base64 data in the parse result metadata.
                vlm_elements = doc_info.metadata.get("vlm_elements", {})

                images = vlm_elements.get("images", [])
                tables = vlm_elements.get("tables", [])
                equations = vlm_elements.get("equations", [])

                # Run VLM analysis
                report = await ctx.analyzer.analyze_document(
                    images=images,
                    tables=tables,
                    equations=equations,
                    enabled_modes=enabled_modes,
                )

                # Store analysis results in doc_status metadata
                analysis_metadata = report.to_metadata_dict()
                await self._doc_status.update_status(
                    doc_id,
                    DocStatus.ANALYZING,
                    metadata={
                        **doc_info.metadata,
                        **analysis_metadata,
                    },
                )

                logger.info(
                    "VLM analysis for doc %s: %d images, %d tables, %d equations",
                    doc_id,
                    len(report.image_results),
                    len(report.table_results),
                    len(report.equation_results),
                )

                # Forward to process queue (enriched with VLM results)
                await q_process.put((doc_info, raw_text))
                await self._pipeline.update_progress(
                    f"Analysed (VLM) {doc_info.content_summary[:50]}",
                    analyzing_delta=-1,
                )

            except PipelineCancelledError:
                await self._doc_status.update_status(
                    doc_id, DocStatus.FAILED, error_msg="Pipeline cancelled"
                )
                await self._pipeline.update_progress(
                    "Pipeline cancelled", failed=1, analyzing_delta=-1
                )
            except Exception as exc:
                logger.exception("VLM analysis failed for doc %s", doc_id)
                # On analysis failure, still forward to process queue
                # so the document can be processed without VLM enrichment.
                logger.info(
                    "Falling back to non-VLM processing for doc %s", doc_id
                )
                await self._doc_status.update_status(
                    doc_id,
                    DocStatus.ANALYZING,
                    metadata={
                        **doc_info.metadata,
                        "vlm_analysis_error": str(exc)[:500],
                    },
                )
                await q_process.put((doc_info, raw_text))
                await self._pipeline.update_progress(
                    f"VLM failed (fallback) {doc_info.content_summary[:50]}: {str(exc)[:80]}",
                    analyzing_delta=-1,
                )
            finally:
                q_analyze.task_done()

    async def _process_worker(
        self,
        q_process: asyncio.Queue[tuple | None],
        ctx: _BatchRunContext,
    ) -> None:
        """Layer 3: Process parsed documents — chunk, extract, merge graph, embed."""
        while True:
            try:
                item = await q_process.get()
            except asyncio.CancelledError:
                return

            if item is None:  # sentinel
                q_process.task_done()
                return

            doc_info, raw_text = item
            doc_id = doc_info.id
            file_path = doc_info.file_path
            kb_name = ctx.kb_name

            async with ctx.semaphore:
                try:
                    self._pipeline.check_cancellation()

                    # Mark as PROCESSING
                    processing_start = time.time()
                    await self._doc_status.update_status(doc_id, DocStatus.PROCESSING)
                    await self._pipeline.update_progress(
                        f"Processing {doc_info.content_summary[:50]}",
                        processing_delta=1,
                    )

                    # Chunk the text
                    chunks = await ctx.chunker.split(
                        raw_text, doc_id=doc_id, file_path=file_path
                    )

                    # Write total chunk count immediately so users see progress
                    total_chunks = len(chunks)
                    await self._doc_status.update_status(
                        doc_id,
                        DocStatus.PROCESSING,
                        chunks_count=total_chunks,
                        metadata={
                            "chunks_processed": 0,
                            "total_chunks": total_chunks,
                            "processing_start_time": processing_start,
                        },
                    )

                    # Check if this document should skip KG extraction.
                    # The ``!`` filename hint (e.g. ``doc.[!].pdf``) sets
                    # ``skip_kg=True`` in the parse options.
                    parse_options = doc_info.metadata.get("parse_options", {})
                    skip_kg = parse_options.get("skip_kg", False)

                    if skip_kg:
                        # Chunking + embedding only — no entity/relation extraction
                        await self._process_skip_kg(
                            kb_name, doc_id, file_path, chunks, processing_start
                        )
                        continue  # finally block calls task_done()

                    from aurora_ext.rag.extraction.types import (
                        GraphEntity,
                        GraphRelationship,
                    )

                    all_entities: dict[str, GraphEntity] = {}
                    all_relationships: dict[tuple[str, str], GraphRelationship] = {}

                    # Extract entities from each chunk
                    for chunk_idx, chunk in enumerate(chunks):
                        self._pipeline.check_cancellation()

                        chunk_key = self._ns(
                            kb_name,
                            f"{NameSpace.KV_STORE_TEXT_CHUNKS}:{doc_id}:{chunk.chunk_index}",
                        )

                        await self._kv.upsert({
                            chunk_key: {
                                "content": chunk.content,
                                "full_doc_id": doc_id,
                                "chunk_order_index": chunk.chunk_index,
                                "tokens": chunk.tokens,
                                "file_path": file_path,
                                "id": chunk_key,
                            }
                        })

                        # LLM extraction (with cache)
                        cache_key = compute_args_hash(
                            "extract", chunk.content, "default"
                        )
                        cache_ns_key = self._ns(
                            kb_name,
                            f"{NameSpace.KV_STORE_LLM_RESPONSE_CACHE}:{cache_key}",
                        )

                        cached = await self._kv.get_by_id(cache_ns_key)
                        if cached:
                            from aurora_ext.rag.extraction.types import (
                                ExtractedEntity,
                                ExtractedRelationship,
                                ExtractionResult,
                            )

                            result_dict = cached["result"]
                            extraction_result = ExtractionResult(
                                entities=[
                                    ExtractedEntity(**e)
                                    for e in result_dict.get("entities", [])
                                ],
                                relationships=[
                                    ExtractedRelationship(**r)
                                    for r in result_dict.get("relationships", [])
                                ],
                                chunk_id=result_dict.get("chunk_id", ""),
                            )
                        else:
                            print(f"\n{'#'*80}\n[SERVICE] About to call extractor for chunk {chunk_key}, use_json=True\n{'#'*80}\n", flush=True)
                            extraction_result = await ctx.extractor.extract(
                                chunk_text=chunk.content,
                                chunk_id=chunk_key,
                                file_path=file_path,
                                use_json=True,
                                language="Chinese",
                            )
                            print(f"[SERVICE] Extractor returned {len(extraction_result.entities)} entities, {len(extraction_result.relationships)} relationships\n", flush=True)
                            from dataclasses import asdict

                            await self._kv.upsert({
                                cache_ns_key: {"result": asdict(extraction_result)}
                            })

                        # Log extraction results
                        logger.info(
                            "Extracted %d entities and %d relationships from chunk %s",
                            len(extraction_result.entities),
                            len(extraction_result.relationships),
                            chunk_key,
                        )

                        # Accumulate entities (per-doc merge)
                        for entity in extraction_result.entities:
                            name_key = entity.entity_name.lower()
                            if name_key in all_entities:
                                existing = all_entities[name_key]
                                desc = existing.description
                                if entity.entity_description not in desc:
                                    desc += f"<SEP>{entity.entity_description}"
                                src = existing.source_id
                                if chunk_key not in src:
                                    src += f"<SEP>{chunk_key}"
                                fp = existing.file_path
                                if file_path and file_path not in fp:
                                    fp += f"<SEP>{file_path}"
                                all_entities[name_key] = GraphEntity(
                                    entity_name=existing.entity_name,
                                    entity_type=existing.entity_type,
                                    description=desc,
                                    source_id=src,
                                    file_path=fp,
                                    weight=existing.weight + 1.0,
                                )
                            else:
                                all_entities[name_key] = GraphEntity(
                                    entity_name=entity.entity_name,
                                    entity_type=entity.entity_type,
                                    description=entity.entity_description,
                                    source_id=chunk_key,
                                    file_path=file_path,
                                    weight=1.0,
                                )

                        # Accumulate relationships (per-doc merge)
                        for rel in extraction_result.relationships:
                            pair_key = tuple(
                                sorted([
                                    rel.source_entity.lower(),
                                    rel.target_entity.lower(),
                                ])
                            )
                            if pair_key in all_relationships:
                                existing = all_relationships[pair_key]
                                desc = existing.description
                                if rel.relationship_description not in desc:
                                    desc += f"<SEP>{rel.relationship_description}"
                                src = existing.source_id
                                if chunk_key not in src:
                                    src += f"<SEP>{chunk_key}"
                                fp = existing.file_path
                                if file_path and file_path not in fp:
                                    fp += f"<SEP>{file_path}"
                                kw = existing.keywords
                                if rel.relationship_keywords not in kw:
                                    kw += f",{rel.relationship_keywords}"
                                all_relationships[pair_key] = GraphRelationship(
                                    source_entity=existing.source_entity,
                                    target_entity=existing.target_entity,
                                    keywords=kw,
                                    description=desc,
                                    source_id=src,
                                    file_path=fp,
                                    weight=existing.weight + 1.0,
                                )
                            else:
                                all_relationships[pair_key] = GraphRelationship(
                                    source_entity=rel.source_entity,
                                    target_entity=rel.target_entity,
                                    keywords=rel.relationship_keywords,
                                    description=rel.relationship_description,
                                    source_id=chunk_key,
                                    file_path=file_path,
                                    weight=1.0,
                                )

                        # Update per-chunk progress (every chunk for responsiveness)
                        chunks_done = chunk_idx + 1
                        if chunks_done % 2 == 0 or chunks_done == total_chunks:
                            await self._doc_status.update_status(
                                doc_id,
                                DocStatus.PROCESSING,
                                chunks_count=total_chunks,
                                metadata={
                                    "chunks_processed": chunks_done,
                                    "total_chunks": total_chunks,
                                    "processing_start_time": processing_start,
                                },
                            )

                    # Log totals before merge
                    logger.info(
                        "Merging %d entities and %d relationships into graph for doc %s",
                        len(all_entities),
                        len(all_relationships),
                        doc_id,
                    )

                    # Merge into graph (serialised via graph_lock)
                    async with ctx.graph_lock:
                        await self._merge_doc_graph(
                            kb_name, all_entities, all_relationships
                        )

                    # Embed chunks and store vectors
                    await self._embed_doc_chunks(
                        kb_name, doc_id, file_path, chunks, all_entities
                    )

                    # Mark as PROCESSED
                    await self._doc_status.update_status(
                        doc_id,
                        DocStatus.PROCESSED,
                        chunks_count=total_chunks,
                        metadata={
                            "processing_start_time": processing_start,
                            "processing_end_time": time.time(),
                            "total_chunks": total_chunks,
                        },
                    )
                    await self._pipeline.update_progress(
                        f"Completed {doc_info.content_summary[:50]}",
                        processed=1,
                        processing_delta=-1,
                    )

                except PipelineCancelledError:
                    logger.info("Pipeline cancelled during doc %s", doc_id)
                    await self._doc_status.update_status(
                        doc_id, DocStatus.FAILED, error_msg="Pipeline cancelled"
                    )
                    await self._pipeline.update_progress(
                        "Pipeline cancelled", failed=1, processing_delta=-1
                    )
                except Exception as exc:
                    logger.exception("Pipeline failed for doc %s", doc_id)
                    await self._doc_status.update_status(
                        doc_id, DocStatus.FAILED, error_msg=str(exc)[:500]
                    )
                    await self._pipeline.update_progress(
                        f"Failed {doc_info.content_summary[:50]}: {str(exc)[:100]}",
                        failed=1,
                        processing_delta=-1,
                    )
                finally:
                    q_process.task_done()

    async def _merge_doc_graph(
        self,
        kb_name: str,
        all_entities: dict,
        all_relationships: dict,
    ) -> None:
        """Merge extracted entities and relationships into the knowledge graph."""
        for entity in all_entities.values():
            node_key = self._ns(kb_name, entity.entity_name)
            existing_node = await self._graph.get_node(node_key)
            if existing_node:
                old_desc = existing_node.get("description", "")
                new_desc = entity.description
                for part in new_desc.split("<SEP>"):
                    if part.strip() and part.strip() not in old_desc:
                        old_desc += f"<SEP>{part.strip()}"
                old_src = existing_node.get("source_id", "")
                for part in entity.source_id.split("<SEP>"):
                    if part.strip() and part.strip() not in old_src:
                        old_src += f"<SEP>{part.strip()}"
                old_fp = existing_node.get("file_path", "")
                if entity.file_path and entity.file_path not in old_fp:
                    old_fp += f"<SEP>{entity.file_path}"
                await self._graph.upsert_node(node_key, {
                    "entity_name": entity.entity_name,
                    "entity_type": entity.entity_type,
                    "description": old_desc,
                    "source_id": old_src,
                    "file_path": old_fp,
                    "weight": float(existing_node.get("weight", 1.0)) + entity.weight,
                })
            else:
                await self._graph.upsert_node(node_key, entity.to_dict())

        for rel in all_relationships.values():
            src_key = self._ns(kb_name, rel.source_entity)
            tgt_key = self._ns(kb_name, rel.target_entity)
            existing_edge = await self._graph.get_edge(src_key, tgt_key)
            if existing_edge:
                old_desc = existing_edge.get("description", "")
                for part in rel.description.split("<SEP>"):
                    if part.strip() and part.strip() not in old_desc:
                        old_desc += f"<SEP>{part.strip()}"
                old_kw = existing_edge.get("keywords", "")
                if rel.keywords and rel.keywords not in old_kw:
                    old_kw += f",{rel.keywords}"
                old_src = existing_edge.get("source_id", "")
                if rel.source_id not in old_src:
                    old_src += f"<SEP>{rel.source_id}"
                await self._graph.upsert_edge(src_key, tgt_key, {
                    "keywords": old_kw,
                    "description": old_desc,
                    "source_id": old_src,
                    "file_path": existing_edge.get("file_path", ""),
                    "weight": float(existing_edge.get("weight", 1.0)) + rel.weight,
                })
            else:
                await self._graph.upsert_edge(src_key, tgt_key, rel.to_dict())

    async def _process_skip_kg(
        self,
        kb_name: str,
        doc_id: str,
        file_path: str,
        chunks: list,
        processing_start: float,
    ) -> None:
        """Process a document with chunking + embedding only (no KG extraction).

        Used when the ``skip_kg`` flag is set via filename hints or metadata.
        Chunks are stored in KV storage and embedded into vector storage, but
        no entity/relation extraction is performed and nothing is merged into
        the knowledge graph.
        """
        total_chunks = len(chunks)

        for chunk_idx, chunk in enumerate(chunks):
            self._pipeline.check_cancellation()

            chunk_key = self._ns(
                kb_name,
                f"{NameSpace.KV_STORE_TEXT_CHUNKS}:{doc_id}:{chunk.chunk_index}",
            )

            await self._kv.upsert({
                chunk_key: {
                    "content": chunk.content,
                    "full_doc_id": doc_id,
                    "chunk_order_index": chunk.chunk_index,
                    "tokens": chunk.tokens,
                    "file_path": file_path,
                    "id": chunk_key,
                }
            })

            chunks_done = chunk_idx + 1
            if chunks_done % 2 == 0 or chunks_done == total_chunks:
                await self._doc_status.update_status(
                    doc_id,
                    DocStatus.PROCESSING,
                    chunks_count=total_chunks,
                    metadata={
                        "chunks_processed": chunks_done,
                        "total_chunks": total_chunks,
                        "processing_start_time": processing_start,
                        "skip_kg": True,
                    },
                )

        # Embed chunks (no entity embedding since there are no entities)
        await self._embed_doc_chunks(kb_name, doc_id, file_path, chunks, {})

        # Mark as PROCESSED
        await self._doc_status.update_status(
            doc_id,
            DocStatus.PROCESSED,
            chunks_count=total_chunks,
            metadata={
                "processing_start_time": processing_start,
                "processing_end_time": time.time(),
                "total_chunks": total_chunks,
                "skip_kg": True,
            },
        )
        await self._pipeline.update_progress(
            f"Completed (skip-KG) {doc_id[:30]}",
            processed=1,
            processing_delta=-1,
        )
        logger.info(
            "Processed doc %s with skip_kg=True (%d chunks, no KG extraction)",
            doc_id,
            total_chunks,
        )

    async def _embed_doc_chunks(
        self,
        kb_name: str,
        doc_id: str,
        file_path: str,
        chunks: list,
        all_entities: dict,
    ) -> None:
        """Embed document chunks and entities, store in vector storage."""
        chunk_texts = [c.content for c in chunks]
        if not chunk_texts:
            return

        embeddings = await self._embedding_func(chunk_texts, is_query=False)
        vector_data: dict[str, dict[str, Any]] = {}
        for i, chunk in enumerate(chunks):
            vkey = self._ns(kb_name, f"chunk:{doc_id}:{chunk.chunk_index}")
            vector_data[vkey] = {
                "content": chunk.content,
                "__vector__": embeddings[i].tolist(),
                "file_path": file_path,
                "full_doc_id": doc_id,
                "chunk_order_index": chunk.chunk_index,
            }
        await self._vector.upsert(vector_data)

        entity_list = list(all_entities.values())
        if entity_list:
            entity_texts = [
                f"{e.entity_name}: {e.description[:200]}" for e in entity_list
            ]
            entity_embeddings = await self._embedding_func(
                entity_texts, is_query=False
            )
            entity_vector_data: dict[str, dict[str, Any]] = {}
            for i, entity in enumerate(entity_list):
                ekey = self._ns(kb_name, entity.entity_name)
                entity_vector_data[ekey] = {
                    "content": f"{entity.entity_name}: {entity.description[:200]}",
                    "__vector__": entity_embeddings[i].tolist(),
                    "entity_name": entity.entity_name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                }
            await self._vector.upsert(entity_vector_data)


    # ── Query ────────────────────────────────────────────────────────

    async def query(
        self,
        kb_name: str,
        *,
        query: str,
        mode: SchemaQueryMode | str = SchemaQueryMode.MIX,
        only_need_context: bool = False,
        only_need_prompt: bool = False,
        response_type: str = "Multiple Paragraphs",
        top_k: int = 40,
        chunk_top_k: int = 20,
        max_entity_tokens: int = 6000,
        max_relation_tokens: int = 8000,
        max_total_tokens: int = 30000,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        user_prompt: str | None = None,
        enable_rerank: bool = False,
        include_references: bool = True,
        include_chunk_content: bool = False,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Execute a RAG query through the QueryEngine."""
        self._try_rebuild_llm()
        self._try_rebuild_embedding()
        self._try_rebuild_query_engine()
        if self._query_engine is None:
            missing = []
            if self._llm is None:
                missing.append("chat model (LLM)")
            if self._embedding_func is None:
                missing.append("embedding model")
            return {
                "error": f"Query unavailable: {' and '.join(missing)} not configured. "
                         f"Please bind them in the Models page first."
            }
        engine_mode = _schema_mode_to_engine(mode)

        # Attach per-KB token tracker to the query params
        tracker = self.get_token_tracker(kb_name)
        tracker_budget = TrackerBudget(
            max_entity_tokens=max_entity_tokens,
            max_relation_tokens=max_relation_tokens,
            max_total_tokens=max_total_tokens,
            max_chunk_tokens=8000,
        )
        tracker.budget = tracker_budget

        param = QueryParam(
            query=query,
            mode=engine_mode,
            only_need_context=only_need_context,
            only_need_prompt=only_need_prompt,
            response_type=response_type,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            max_entity_tokens=max_entity_tokens,
            max_relation_tokens=max_relation_tokens,
            max_total_tokens=max_total_tokens,
            max_chunk_tokens=8000,
            token_tracker=tracker,
            hl_keywords=hl_keywords or [],
            ll_keywords=ll_keywords or [],
            conversation_history=conversation_history or [],
            user_prompt=user_prompt,
            enable_rerank=enable_rerank,
            include_references=include_references,
            include_chunk_content=include_chunk_content,
            stream=stream,
        )
        result = await self._query_engine.query(param)

        output: dict[str, Any] = {
            "response": result.response,
            "entities": result.entities,
            "relationships": result.relationships,
            "chunks": result.chunks,
            "references": result.references,
            "hl_keywords": result.hl_keywords,
            "ll_keywords": result.ll_keywords,
        }

        if result.is_streaming and result.stream_iterator is not None:
            output["stream_iterator"] = result.stream_iterator

        return output

    # ── LLM Pass-Through ────────────────────────────────────────────

    async def llm_generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Direct LLM pass-through (no retrieval) for the Ollama generate endpoint."""
        from aurora_core.schema.message import Message

        self._try_rebuild_llm()
        if self._llm is None:
            return {"error": "Chat model (LLM) not configured. Please bind a chat model in the Models page first."}

        messages: list[Message] = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        if stream:
            iterator = self._llm.achat_stream(messages)
            return {"stream_iterator": iterator}

        output = await self._llm.achat(messages)
        return {"response": output.text}

    # ── Document Ingestion ───────────────────────────────────────────

    async def upload_file(self, kb_name: str, file: UploadFile) -> InsertResponse:
        """Upload a file and register it for pipeline processing."""
        track_id = uuid.uuid4().hex
        file_content = await file.read()
        filename = file.filename or f"upload_{track_id}"

        # ── Filename dedup ───────────────────────────────────────────
        basename = os.path.basename(filename)
        existing_by_name = await self._doc_status.get_doc_by_basename(
            basename, kb_name=kb_name
        )
        if existing_by_name is not None:
            return InsertResponse(
                status=InsertStatusEnum.SUCCESS,
                message=(
                    f"Duplicate filename detected "
                    f"('{basename}' already exists as "
                    f"'{existing_by_name.file_path}')"
                ),
                track_id=existing_by_name.track_id,
            )

        # ── Content-hash dedup (C17) ────────────────────────────────
        text_for_hash = (
            file_content.decode("utf-8", errors="replace")
            if isinstance(file_content, (bytes, bytearray))
            else file_content
        )
        content_hash = compute_mdhash_id(text_for_hash)
        hash_key = self._ns(kb_name, f"hash:{content_hash}")
        existing = await self._kv.get_by_id(hash_key)
        if existing:
            # Verify the referenced document still exists in doc_status
            old_track_id = existing.get("track_id", "")
            if old_track_id:
                old_doc = await self._doc_status.get_status(old_track_id)
                if old_doc is not None:
                    return InsertResponse(
                        status=InsertStatusEnum.SUCCESS,
                        message=(
                            f"Duplicate document detected "
                            f"(same content as '{existing.get('file_path', 'unknown')}')"
                        ),
                        track_id=old_track_id,
                    )
            # Old record was deleted — remove stale hash and proceed
            await self._kv.delete([hash_key])

        input_path = Path(self._input_dir)
        input_path.mkdir(parents=True, exist_ok=True)
        dest = input_path / filename
        dest.write_bytes(file_content)

        # Store hash for future dedup
        await self._kv.upsert({
            hash_key: {"file_path": str(dest), "track_id": track_id}
        })

        # Parse filename hints (e.g. ``doc.[!].pdf`` → skip_kg=True)
        from aurora_ext.rag.parser.routing import parse_filename_hints

        parse_options = parse_filename_hints(filename)

        doc_info = DocStatusInfo(
            id=track_id,
            file_path=str(dest),
            status=DocStatus.PENDING,
            content_summary=filename,
            content_length=len(file_content),
            track_id=track_id,
            kb_name=kb_name,
            content_hash=content_hash,
            basename=os.path.basename(filename),
            metadata={"parse_options": parse_options},
        )
        await self._doc_status.upsert({track_id: doc_info})

        # Trigger the ingestion pipeline in the background so the HTTP
        # response returns immediately.  The frontend polls pipeline_status
        # to show real-time progress.
        logger.info("📤 About to spawn pipeline task for kb=%s track_id=%s", kb_name, track_id)
        task = self._spawn_task(self._process_pending_documents(kb_name, track_id))
        logger.info("✅ Pipeline task spawned: %s, active_tasks=%d", task.get_name(), len(self._active_tasks))

        return InsertResponse(
            status=InsertStatusEnum.SUCCESS,
            message=f"File '{filename}' uploaded and queued for processing",
            track_id=track_id,
        )

    async def insert_text(
        self, kb_name: str, text: str, *, file_source: str | None = None
    ) -> InsertResponse:
        """Insert a single text document."""
        track_id = uuid.uuid4().hex
        doc_info = DocStatusInfo(
            id=track_id,
            file_path=file_source or "",
            status=DocStatus.PENDING,
            content_summary=text[:200],
            content_length=len(text),
            track_id=track_id,
            kb_name=kb_name,
        )
        await self._doc_status.upsert({track_id: doc_info})

        # Store the text content in KV storage for pipeline pickup (namespaced)
        await self._kv.upsert({
            self._ns(kb_name, track_id): {
                "content": text,
                "file_path": file_source or "",
                "id": track_id,
            }
        })

        # Trigger the ingestion pipeline in the background
        self._spawn_task(self._process_pending_documents(kb_name, track_id))

        return InsertResponse(
            status=InsertStatusEnum.SUCCESS,
            message="Text document queued for processing",
            track_id=track_id,
        )

    async def insert_texts(
        self,
        kb_name: str,
        texts: list[str],
        *,
        file_sources: list[str] | None = None,
    ) -> InsertResponse:
        """Batch-insert multiple text documents."""
        track_id = uuid.uuid4().hex
        statuses: dict[str, DocStatusInfo] = {}
        kv_data: dict[str, dict[str, Any]] = {}

        for i, text in enumerate(texts):
            doc_id = f"{track_id}_{i}"
            source = file_sources[i] if file_sources and i < len(file_sources) else ""
            statuses[doc_id] = DocStatusInfo(
                id=doc_id,
                file_path=source,
                status=DocStatus.PENDING,
                content_summary=text[:200],
                content_length=len(text),
                track_id=track_id,
                kb_name=kb_name,
            )
            kv_data[self._ns(kb_name, doc_id)] = {
                "content": text,
                "file_path": source,
                "id": doc_id,
            }

        await self._doc_status.upsert(statuses)
        await self._kv.upsert(kv_data)

        # Trigger the ingestion pipeline in the background
        self._spawn_task(self._process_pending_documents(kb_name, track_id))

        return InsertResponse(
            status=InsertStatusEnum.SUCCESS,
            message=f"{len(texts)} text documents queued for processing",
            track_id=track_id,
        )

    # ── Pipeline ─────────────────────────────────────────────────────

    async def scan_directory(self, kb_name: str) -> ScanResponse:
        """Scan the input directory for new documents to ingest."""
        if self._pipeline.is_busy:
            return ScanResponse(
                status=ScanStatusEnum.SCANNING_SKIPPED_PIPELINE_BUSY,
                message="Pipeline is busy, scan skipped",
                track_id="",
            )

        track_id = uuid.uuid4().hex
        input_path = Path(self._input_dir)
        if not input_path.exists():
            return ScanResponse(
                status=ScanStatusEnum.SCANNING_STARTED,
                message="Input directory does not exist, nothing to scan",
                track_id=track_id,
            )

        # Discover files and register them as pending
        supported_extensions = {
            ".txt", ".md", ".pdf", ".docx", ".pptx",
            ".xlsx", ".csv", ".json", ".html", ".htm",
        }
        files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]

        if not files:
            return ScanResponse(
                status=ScanStatusEnum.SCANNING_STARTED,
                message="No supported files found in input directory",
                track_id=track_id,
            )

        statuses: dict[str, DocStatusInfo] = {}
        for file_path in files:
            doc_id = uuid.uuid4().hex
            statuses[doc_id] = DocStatusInfo(
                id=doc_id,
                file_path=str(file_path),
                status=DocStatus.PENDING,
                content_summary=file_path.name,
                content_length=file_path.stat().st_size,
                track_id=track_id,
                kb_name=kb_name,
            )

        await self._doc_status.upsert(statuses)

        # Trigger the ingestion pipeline in the background
        self._spawn_task(self._process_pending_documents(kb_name, track_id))

        return ScanResponse(
            status=ScanStatusEnum.SCANNING_STARTED,
            message=f"Scan started: {len(files)} files queued for processing",
            track_id=track_id,
        )

    async def get_pipeline_status(self, kb_name: str) -> PipelineStatusResponse:
        """Return the current pipeline state."""
        status_dict = await self._pipeline.get_status_dict()
        return PipelineStatusResponse(**status_dict)

    async def cancel_pipeline(self, kb_name: str) -> bool:
        """Request cancellation of the running pipeline."""
        return await self._pipeline.cancel()

    # ── Document Status ──────────────────────────────────────────────

    async def get_status_counts(self, kb_name: str) -> StatusCountsResponse:
        """Get document counts grouped by status, scoped to this knowledge base."""
        counts = await self._doc_status.get_status_counts(kb_name=kb_name)
        return StatusCountsResponse(counts=counts)

    async def get_documents_paginated(
        self,
        kb_name: str,
        *,
        status_filter: DocStatusEnum | None = None,
        status_filters: list[DocStatusEnum] | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "created_at",
        sort_direction: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated document listing with optional status filters."""
        core_filters: list[DocStatus] | None = None
        if status_filters:
            core_filters = [
                s for f in status_filters if (s := _schema_status_to_core(f)) is not None
            ]
        elif status_filter is not None:
            mapped = _schema_status_to_core(status_filter)
            if mapped is not None:
                core_filters = [mapped]

        docs, total = await self._doc_status.get_all_docs(
            status_filters=core_filters,
            page=page,
            page_size=page_size,
            sort_field=sort_field,
            sort_direction=sort_direction,
            kb_name=kb_name,
        )
        return [_doc_status_to_dict(d) for d in docs], total

    async def get_docs_by_track_id(self, kb_name: str, track_id: str) -> list[dict[str, Any]]:
        """Get all documents belonging to a tracking batch."""
        results = await self._doc_status.get_all_docs(
            page=1, page_size=10000, kb_name=kb_name
        )
        docs, _ = results
        matched = [d for d in docs if d.track_id == track_id]
        return [_doc_status_to_dict(d) for d in matched]

    # ── Delete ───────────────────────────────────────────────────────

    # Statuses that indicate active pipeline processing
    _ACTIVE_STATUSES = {
        DocStatus.PARSING,
        DocStatus.ANALYZING,
        DocStatus.PREPROCESSED,
        DocStatus.PROCESSING,
    }

    async def delete_documents(
        self,
        kb_name: str,
        *,
        doc_ids: list[str],
        delete_file: bool = False,
        delete_llm_cache: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Delete documents, optionally removing files and LLM cache.

        When *force* is False (default), documents that are actively being
        processed (PARSING, ANALYZING, PREPROCESSED, PROCESSING) will be
        rejected.  Pass *force=True* to override this safety check (the
        caller is responsible for cancelling the pipeline first).
        """
        deleted_ids: list[str] = []
        errors: list[str] = []
        blocked_ids: list[str] = []

        for doc_id in doc_ids:
            try:
                info = await self._doc_status.get_status(doc_id)
                if info is None:
                    errors.append(f"Document '{doc_id}' not found")
                    continue

                # Safety check: reject deletion of actively processing docs
                if not force and info.status in self._ACTIVE_STATUSES:
                    blocked_ids.append(doc_id)
                    continue

                if delete_file and info.file_path:
                    p = Path(info.file_path)
                    if p.exists():
                        p.unlink()

                await self._doc_status.delete([doc_id])
                deleted_ids.append(doc_id)
            except Exception as exc:
                errors.append(f"Error deleting '{doc_id}': {exc}")

        return {
            "deleted": deleted_ids,
            "errors": errors,
            "blocked": blocked_ids,
            "success": len(errors) == 0 and len(blocked_ids) == 0,
        }

    async def clear_llm_cache(self, kb_name: str) -> bool:
        """Clear the LLM response cache namespace."""
        try:
            await self._kv.drop()
            return True
        except Exception:
            logger.exception("Failed to clear LLM cache")
            return False

    async def reprocess_all(self, kb_name: str) -> dict[str, Any]:
        """Re-queue ALL documents (including PROCESSED) for reprocessing.

        Useful when the LLM cache was corrupted and entities need to be
        re-extracted from scratch.
        """
        all_docs, _total = await self._doc_status.get_all_docs(
            kb_name=kb_name, page_size=99999
        )
        if not all_docs:
            return {"requeued": 0, "message": "No documents to reprocess"}

        # Clear the LLM cache first
        await self._kv.drop()
        logger.info("Cleared LLM cache for KB '%s' before full reprocess", kb_name)

        reprocess_track_id = uuid.uuid4().hex
        requeue_ids: list[str] = []
        for info in all_docs:
            updated_info = DocStatusInfo(
                id=info.id,
                file_path=info.file_path,
                status=DocStatus.PENDING,
                content_summary=info.content_summary,
                content_length=info.content_length,
                track_id=reprocess_track_id,
                kb_name=kb_name,
            )
            await self._doc_status.upsert({info.id: updated_info})
            requeue_ids.append(info.id)

        self._spawn_task(self._process_pending_documents(kb_name, reprocess_track_id))

        return {
            "requeued": len(requeue_ids),
            "doc_ids": requeue_ids,
            "track_id": reprocess_track_id,
            "message": f"Cleared cache and re-queued {len(requeue_ids)} documents",
        }

    async def reprocess_failed(self, kb_name: str) -> dict[str, Any]:
        """Re-queue all failed documents for reprocessing (scoped to this KB)."""
        failed = await self._doc_status.get_docs_by_status(
            DocStatus.FAILED, kb_name=kb_name
        )
        if not failed:
            return {"requeued": 0, "message": "No failed documents to reprocess"}

        # Assign a new track_id so the pipeline can pick them up as a batch
        reprocess_track_id = uuid.uuid4().hex
        requeue_ids: list[str] = []
        for info in failed:
            # Re-register with the new track_id so the pipeline can find them
            updated_info = DocStatusInfo(
                id=info.id,
                file_path=info.file_path,
                status=DocStatus.PENDING,
                content_summary=info.content_summary,
                content_length=info.content_length,
                track_id=reprocess_track_id,
                kb_name=kb_name,
            )
            await self._doc_status.upsert({info.id: updated_info})
            requeue_ids.append(info.id)

        # Trigger the ingestion pipeline in the background (D)
        self._spawn_task(self._process_pending_documents(kb_name, reprocess_track_id))

        return {
            "requeued": len(requeue_ids),
            "doc_ids": requeue_ids,
            "track_id": reprocess_track_id,
            "message": f"{len(requeue_ids)} documents re-queued for processing",
        }

    # ── Graph Operations ─────────────────────────────────────────────

    async def get_all_labels(self, kb_name: str) -> list[str]:
        """Return all entity labels."""
        return await self._graph.get_all_labels()

    async def get_popular_labels(self, kb_name: str, *, limit: int = 300) -> list[str]:
        """Return labels ordered by node degree."""
        return await self._graph.get_popular_labels(limit=limit)

    async def search_labels(self, kb_name: str, *, query: str, limit: int = 50) -> list[str]:
        """Fuzzy-search entity labels."""
        return await self._graph.search_labels(query=query, limit=limit)

    async def get_subgraph(
        self, kb_name: str, *, label: str, max_depth: int = 3, max_nodes: int = 1000
    ) -> dict[str, Any]:
        """Get a connected subgraph from a starting label."""
        return await self._graph.get_connected_subgraph(
            label=label, max_depth=max_depth, max_nodes=max_nodes
        )

    async def entity_exists(self, kb_name: str, *, entity_name: str) -> bool:
        """Check whether an entity exists."""
        return await self._graph.has_node(entity_name)

    async def update_entity(
        self,
        kb_name: str,
        *,
        entity_name: str,
        updated_data: dict[str, Any],
        allow_rename: bool = False,
        allow_merge: bool = False,
    ) -> dict[str, Any]:
        """Update an existing entity's properties.

        Handles optional renaming and merge-on-conflict logic.
        """
        if not await self._graph.has_node(entity_name):
            raise ValueError(f"Entity '{entity_name}' does not exist")

        new_name = updated_data.get("entity_name", entity_name)
        renamed = new_name != entity_name

        if renamed and not allow_rename:
            raise ValueError(
                "Renaming requires allow_rename=True. "
                f"Cannot rename '{entity_name}' to '{new_name}'"
            )

        if renamed and await self._graph.has_node(new_name):
            if not allow_merge:
                raise ValueError(
                    f"Entity '{new_name}' already exists. "
                    "Use allow_merge=True or the merge endpoint."
                )
            # Perform merge
            return await self.merge_entities(
                kb_name,
                entities_to_change=[entity_name],
                entity_to_change_into=new_name,
            )

        if renamed:
            # Copy node data to new name, delete old
            old_data = await self._graph.get_node(entity_name)
            merged_data = {**(old_data or {}), **updated_data}
            merged_data["entity_name"] = new_name
            await self._graph.upsert_node(new_name, merged_data)

            # Re-wire edges
            edges = await self._graph.get_node_edges(entity_name)
            for src, tgt in edges:
                edge_data = await self._graph.get_edge(src, tgt)
                new_src = new_name if src == entity_name else src
                new_tgt = new_name if tgt == entity_name else tgt
                if edge_data:
                    await self._graph.upsert_edge(new_src, new_tgt, edge_data)
                await self._graph.delete_edge(src, tgt)

            await self._graph.delete_node(entity_name)
            return {
                "renamed": True,
                "final_entity": new_name,
                "operation_status": "success",
                "merge_status": "",
                "merged": False,
            }

        # Simple update in-place
        existing = await self._graph.get_node(entity_name) or {}
        merged = {**existing, **updated_data}
        await self._graph.upsert_node(entity_name, merged)
        return {
            "renamed": False,
            "final_entity": entity_name,
            "operation_status": "success",
            "merge_status": "",
            "merged": False,
        }

    async def create_entity(
        self,
        kb_name: str,
        *,
        entity_name: str,
        entity_type: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new entity."""
        if await self._graph.has_node(entity_name):
            raise ValueError(f"Entity '{entity_name}' already exists")

        node_data: dict[str, Any] = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "description": description,
            "source_id": "",
        }
        if metadata:
            node_data.update(metadata)

        await self._graph.upsert_node(entity_name, node_data)
        return {
            "operation_status": "success",
            "final_entity": entity_name,
            "renamed": False,
            "merged": False,
            "merge_status": "",
        }

    async def create_relation(
        self,
        kb_name: str,
        *,
        source_entity: str,
        target_entity: str,
        relation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new relationship."""
        if not await self._graph.has_node(source_entity):
            raise ValueError(f"Source entity '{source_entity}' does not exist")
        if not await self._graph.has_node(target_entity):
            raise ValueError(f"Target entity '{target_entity}' does not exist")

        if await self._graph.has_edge(source_entity, target_entity):
            raise ValueError(
                f"Relationship '{source_entity}' -> '{target_entity}' already exists"
            )

        edge_data: dict[str, Any] = {
            "src_id": source_entity,
            "tgt_id": target_entity,
            "source_id": "",
            **relation_data,
        }
        await self._graph.upsert_edge(source_entity, target_entity, edge_data)
        return {
            "operation_status": "success",
            "final_entity": source_entity,
            "target_entity": target_entity,
            "renamed": False,
            "merged": False,
            "merge_status": "",
        }

    async def update_relation(
        self,
        kb_name: str,
        *,
        source_entity: str,
        target_entity: str,
        updated_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing relationship."""
        if not await self._graph.has_edge(source_entity, target_entity):
            raise ValueError(
                f"Relationship '{source_entity}' -> '{target_entity}' does not exist"
            )

        existing = await self._graph.get_edge(source_entity, target_entity) or {}
        merged = {**existing, **updated_data}
        merged["src_id"] = source_entity
        merged["tgt_id"] = target_entity
        await self._graph.upsert_edge(source_entity, target_entity, merged)
        return {
            "operation_status": "success",
            "final_entity": source_entity,
            "target_entity": target_entity,
            "renamed": False,
            "merged": False,
            "merge_status": "",
        }

    async def merge_entities(
        self,
        kb_name: str,
        *,
        entities_to_change: list[str],
        entity_to_change_into: str,
        merge_strategy: str = "join_unique",
    ) -> dict[str, Any]:
        """Merge multiple entities into a single target entity.

        Uses :class:`GraphManager` with configurable merge strategies:

        - ``concatenate`` — join all values with field separator.
        - ``keep_first``  — keep target values, discard source values.
        - ``join_unique`` — join only values not already present (default).

        All edges from the source entities are re-wired to the target.
        Source entities are deleted after merging.
        """
        from aurora_ext.rag.knowledge.graph_manager import (
            GraphManager,
            MergeStrategy,
        )

        strategy_map = {
            "concatenate": MergeStrategy.CONCATENATE,
            "keep_first": MergeStrategy.KEEP_FIRST,
            "join_unique": MergeStrategy.JOIN_UNIQUE,
        }
        strategy = strategy_map.get(merge_strategy, MergeStrategy.JOIN_UNIQUE)

        manager = GraphManager(
            graph_storage=self._graph,
            vector_storage=self._vector,
            embedding_func=self._embedding_func,
        )

        result = await manager.merge_entities(
            target_entity=entity_to_change_into,
            source_entities=entities_to_change,
            strategy=strategy,
        )

        if not result.success:
            return {
                "merged": result.merged_count > 0,
                "merge_status": "partial",
                "operation_status": "partial_success",
                "renamed": False,
                "final_entity": entity_to_change_into,
            }

        return {
            "merged": True,
            "merge_status": "success",
            "operation_status": "success",
            "renamed": False,
            "final_entity": entity_to_change_into,
        }

    async def delete_entity(self, kb_name: str, entity_id: str) -> None:
        """Delete an entity and all its edges from the knowledge graph."""
        # kb_name reserved for multi-KB storage scoping
        await self._graph.delete_node(entity_id)

    async def delete_relation(
        self, kb_name: str, source_id: str, target_id: str
    ) -> None:
        """Delete a relationship between two entities."""
        # kb_name reserved for multi-KB storage scoping
        await self._graph.delete_edge(source_id, target_id)

    # ── Graph Import ─────────────────────────────────────────────────

    async def import_graph(
        self,
        kb_name: str,
        *,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        merge_strategy: str = "merge",
    ) -> dict[str, Any]:
        """Batch-import entities and relationships into the knowledge graph.

        Parameters
        ----------
        kb_name:
            Knowledge base name for multi-KB scoping.
        entities:
            List of entity dicts (from JSON or parsed YAML).
        relationships:
            List of relationship dicts (from JSON or parsed YAML).
        merge_strategy:
            Conflict resolution: ``overwrite``, ``merge``, or ``skip``.

        Returns
        -------
        dict
            Injection statistics: created/updated/skipped counts and errors.
        """
        from aurora_ext.rag.injection.custom_kg_injector import (
            CustomKGInjector,
            MergeStrategy,
        )

        strategy_map = {
            "overwrite": MergeStrategy.OVERWRITE,
            "merge": MergeStrategy.MERGE,
            "skip": MergeStrategy.SKIP,
        }
        strategy = strategy_map.get(merge_strategy, MergeStrategy.MERGE)

        import_entities = CustomKGInjector.parse_entities_from_dict(entities)
        import_relationships = CustomKGInjector.parse_relationships_from_dict(
            relationships
        )

        if not import_entities and not import_relationships:
            return {
                "status": "success",
                "message": "No valid entities or relationships to import",
                "stats": {
                    "entities_created": 0,
                    "entities_updated": 0,
                    "entities_skipped": 0,
                    "relationships_created": 0,
                    "relationships_updated": 0,
                    "relationships_skipped": 0,
                    "errors": [],
                },
            }

        self._try_rebuild_embedding()

        injector = CustomKGInjector(
            graph_storage=self._graph,
            vector_storage=self._vector,
            embedding_func=self._embedding_func,
        )

        stats = await injector.inject(
            entities=import_entities,
            relationships=import_relationships,
            strategy=strategy,
            kb_name=kb_name,
        )

        total = stats.total_entities + stats.total_relationships
        return {
            "status": "success" if not stats.errors else "partial_success",
            "message": (
                f"Imported {total} items: "
                f"{stats.entities_created} entities created, "
                f"{stats.entities_updated} updated, "
                f"{stats.entities_skipped} skipped; "
                f"{stats.relationships_created} relationships created, "
                f"{stats.relationships_updated} updated, "
                f"{stats.relationships_skipped} skipped"
                + (f"; {len(stats.errors)} errors" if stats.errors else "")
            ),
            "stats": stats.to_dict(),
        }

    # ── KG Export ────────────────────────────────────────────────────

    async def export_graph(
        self,
        kb_name: str,
        *,
        export_format: str = "csv",
        export_scope: str = "all",
        include_embeddings: bool = False,
        entity_filter: list[str] | None = None,
        max_entities: int = 0,
        max_relationships: int = 0,
    ) -> dict[str, Any]:
        """Export knowledge graph data in the specified format.

        Parameters
        ----------
        kb_name:
            Knowledge base name for multi-KB scoping.
        export_format:
            Output format: csv, excel, markdown, txt.
        export_scope:
            What to export: all, entities, relationships.
        include_embeddings:
            Whether to include vector embedding data.
        entity_filter:
            Optional list of entity names to filter by.
        max_entities:
            Maximum number of entities (0 = unlimited).
        max_relationships:
            Maximum number of relationships (0 = unlimited).

        Returns
        -------
        dict
            Export result with content bytes, filename, mime_type, and counts.
        """
        from aurora_ext.rag.knowledge.kg_exporter import (
            ExportFormat,
            ExportOptions,
            ExportScope,
            KGExporter,
        )

        format_map = {
            "csv": ExportFormat.CSV,
            "excel": ExportFormat.EXCEL,
            "markdown": ExportFormat.MARKDOWN,
            "txt": ExportFormat.TXT,
        }
        scope_map = {
            "all": ExportScope.ALL,
            "entities": ExportScope.ENTITIES_ONLY,
            "relationships": ExportScope.RELATIONSHIPS_ONLY,
        }

        fmt = format_map.get(export_format, ExportFormat.CSV)
        scope = scope_map.get(export_scope, ExportScope.ALL)

        options = ExportOptions(
            format=fmt,
            scope=scope,
            include_embeddings=include_embeddings,
            entity_filter=entity_filter or [],
            max_entities=max_entities,
            max_relationships=max_relationships,
        )

        exporter = KGExporter(
            graph_storage=self._graph,
            vector_storage=self._vector,
        )

        result = await exporter.export(options, kb_name=kb_name)

        return {
            "content": result.content,
            "filename": result.filename,
            "mime_type": result.mime_type,
            "entity_count": result.entity_count,
            "relationship_count": result.relationship_count,
        }

    # ── Token Budget Stats ─────────────────────────────────────────────

    def get_token_tracker(self, kb_name: str) -> TokenTracker:
        """Return (or lazily create) the token tracker for a knowledge base."""
        if kb_name not in self._token_trackers:
            self._token_trackers[kb_name] = TokenTracker(TrackerBudget())
        return self._token_trackers[kb_name]

    def get_token_stats(self, kb_name: str) -> dict[str, Any]:
        """Return token usage statistics for a knowledge base."""
        tracker = self.get_token_tracker(kb_name)
        return tracker.get_stats()

    def reset_token_stats(self, kb_name: str) -> bool:
        """Reset token usage statistics for a knowledge base."""
        tracker = self._token_trackers.get(kb_name)
        if tracker is None:
            return False
        tracker.reset_stats()
        return True

    # ── RAGAS Evaluation ──────────────────────────────────────────────

    async def evaluate(
        self,
        kb_name: str,
        *,
        items: list[dict[str, Any]],
        metrics: list[str] | None = None,
        auto_retrieve: bool = False,
        query_mode: SchemaQueryMode | str = SchemaQueryMode.MIX,
    ) -> dict[str, Any]:
        """Evaluate RAG quality using the RAGAS framework.

        For each item, the evaluator computes faithfulness, answer
        relevancy, context precision, and (optionally) context recall.

        When ``auto_retrieve`` is True and an item has no contexts, the
        service queries this knowledge base to populate them and also
        generates a fresh answer if the provided answer is empty.
        """
        from aurora_ext.rag.evaluation import (
            EvaluationItem,
            RAGASEvaluator,
            wrap_embeddings,
            wrap_llm,
        )

        # Build EvaluationItem list, optionally auto-retrieving contexts
        eval_items: list[EvaluationItem] = []
        for item_dict in items:
            query = item_dict.get("query", "")
            answer = item_dict.get("answer", "")
            contexts = item_dict.get("contexts", [])
            ground_truth = item_dict.get("ground_truth")

            if auto_retrieve and not contexts:
                query_result = await self.query(
                    kb_name,
                    query=query,
                    mode=query_mode,
                    only_need_context=True,
                    stream=False,
                )
                # Extract chunk content from query result
                chunks = query_result.get("chunks", [])
                contexts = [
                    c.get("content", str(c)) if isinstance(c, dict) else str(c)
                    for c in chunks
                ]

                # If no answer provided, use the RAG-generated one
                if not answer:
                    answer = query_result.get("response", "")

            eval_items.append(
                EvaluationItem(
                    query=query,
                    answer=answer,
                    contexts=contexts,
                    ground_truth=ground_truth,
                )
            )

        # Wrap Aurora LLM/Embeddings as LangChain interfaces for RAGAS
        self._try_rebuild_llm()
        self._try_rebuild_embedding()

        lc_llm = None
        lc_embeddings = None

        if self._llm is not None:
            try:
                lc_llm = wrap_llm(self._llm)
            except ImportError:
                logger.warning(
                    "langchain_core not installed — RAGAS will use its "
                    "default model configuration"
                )
            except Exception:
                logger.exception("Failed to wrap Aurora LLM for RAGAS")

        if self._embedding_func is not None:
            try:
                # The embedding_func wraps a callable — unwrap the
                # underlying BaseEmbeddings from the registry
                if self._registry is not None:
                    try:
                        raw_emb = self._registry.get_embeddings()
                        lc_embeddings = wrap_embeddings(raw_emb)
                    except RuntimeError:
                        pass
            except ImportError:
                logger.warning(
                    "langchain_core not installed — RAGAS will use its "
                    "default embedding configuration"
                )
            except Exception:
                logger.exception(
                    "Failed to wrap Aurora embeddings for RAGAS"
                )

        evaluator = RAGASEvaluator(llm=lc_llm, embeddings=lc_embeddings)
        report = evaluator.evaluate(eval_items, metrics=metrics)
        return report.to_dict()

    # ── Extraction configuration (Phase 5+) ─────────────────────────

    # Per-knowledge-base extraction config store.  Keyed by ``kb_name``.
    _extraction_configs: dict[str, Any] | None = None

    def _ensure_extraction_configs(self) -> dict[str, Any]:
        if self._extraction_configs is None:
            self._extraction_configs = {}
        return self._extraction_configs

    def get_extraction_config(self, kb_name: str) -> Any:
        """Return the :class:`KGExtractionFullConfig` for *kb_name*.

        Falls back to sensible defaults when no custom config has been
        set for the given knowledge base.
        """
        from aurora_ext.rag.extraction.config import KGExtractionFullConfig

        store = self._ensure_extraction_configs()
        if kb_name not in store:
            store[kb_name] = KGExtractionFullConfig()
        return store[kb_name]

    def update_extraction_config(
        self,
        kb_name: str,
        updates: dict[str, Any],
    ) -> Any:
        """Partially update the extraction config for *kb_name*.

        Returns the updated :class:`KGExtractionFullConfig`.
        """
        from dataclasses import replace as _dc_replace

        from aurora_ext.rag.extraction.config import (
            AddonParams,
            ExtractionConfig,
            EntityTypeConfig,
            KGExtractionFullConfig,
        )

        current = self.get_extraction_config(kb_name)
        store = self._ensure_extraction_configs()

        # Build updated sub-configs.
        ext_fields = {
            f: updates[f]
            for f in (
                "entity_extract_max_gleaning",
                "relation_extract_max_gleaning",
                "max_parallel_extract",
                "enable_incremental_extract",
                "max_total_records",
                "max_entity_records",
                "use_json",
                "enable_cache",
            )
            if f in updates
        }
        new_ext = _dc_replace(current.extraction, **ext_fields) if ext_fields else current.extraction

        # Entity types.
        et_data = updates.get("entity_types")
        if et_data:
            custom_types = et_data.get("custom_types", current.entity_types.custom_types)
            if isinstance(custom_types, list):
                custom_types = tuple(custom_types)
            new_et = _dc_replace(
                current.entity_types,
                custom_types=custom_types,
                type_prompt_file=et_data.get(
                    "type_prompt_file", current.entity_types.type_prompt_file
                ),
            )
        else:
            new_et = current.entity_types

        # Relation types.
        rt_data = updates.get("relation_types")
        if rt_data:
            custom_rel = rt_data.get("custom_types", current.entity_types.custom_relation_types)
            if isinstance(custom_rel, list):
                custom_rel = tuple(custom_rel)
            new_et = _dc_replace(new_et, custom_relation_types=custom_rel)

        # Addon / language.
        addon_fields: dict[str, Any] = {}
        lang_data = updates.get("language")
        if lang_data and isinstance(lang_data, dict):
            addon_fields["language"] = lang_data.get(
                "output_language", current.addon.language
            )
        for key in ("entity_types_guidance", "relation_types_guidance"):
            if key in updates:
                addon_fields[key] = updates[key]
        new_addon = (
            _dc_replace(current.addon, **addon_fields)
            if addon_fields
            else current.addon
        )

        merged = KGExtractionFullConfig(
            extraction=new_ext,
            entity_types=new_et,
            addon=new_addon,
        )
        store[kb_name] = merged
        return merged

    async def batch_extract(
        self,
        kb_name: str,
        chunks: list[dict[str, str]],
    ) -> Any:
        """Run batch concurrent extraction on *chunks* for *kb_name*.

        Uses the :class:`ExtractionOrchestrator` with the per-KB
        extraction configuration.
        """
        from aurora_ext.rag.extraction.config import KGExtractionFullConfig
        from aurora_ext.rag.extraction.extractor import EntityRelationExtractor
        from aurora_ext.rag.extraction.orchestrator import ExtractionOrchestrator

        cfg: KGExtractionFullConfig = self.get_extraction_config(kb_name)

        # Build an extractor using the KB's LLM (extract role).
        self._try_rebuild_llm()
        llm = self._llm
        if llm is None and self._role_registry is not None:
            from aurora_core.model.roles import LLMRole
            try:
                llm = await self._role_registry.get_llm(LLMRole.EXTRACT)
            except Exception:
                llm = None

        if llm is None:
            raise RuntimeError(
                "No LLM available for extraction. "
                "Configure a default LLM or bind the extract role."
            )

        extractor = EntityRelationExtractor(llm=llm)
        orchestrator = ExtractionOrchestrator.from_full_config(extractor, cfg)
        return await orchestrator.extract_batch(chunks)
