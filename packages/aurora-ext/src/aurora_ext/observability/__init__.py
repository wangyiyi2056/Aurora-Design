"""Langfuse observability integration for Aurora RAG.

Provides automatic tracing of LLM calls, embeddings, KG extraction,
RAG queries, and reranker operations via the Langfuse platform.

Quick start::

    from aurora_ext.observability import (
        LangfuseConfig,
        LangfuseClient,
        load_langfuse_config,
        get_langfuse_client,
        trace_llm,
        trace_embedding,
        trace_rag_query,
        trace_kg_extraction,
        trace_reranker,
        trace_operation,
        trace_span,
        trace_generation,
        nested_span,
        ObservabilityBridge,
    )

    # 1. Load config from env vars and/or TOML
    config = load_langfuse_config()

    # 2. Initialise the singleton client
    client = get_langfuse_client(config)
    client.initialise()

    # 3a. Use decorators
    @trace_llm
    async def my_llm_call(messages, model="gpt-4o"):
        ...

    # 3b. Use context managers
    with trace_span("kg-extraction", kb_name="default") as ctx:
        results = await extract(...)
        ctx.add_metadata("entity_count", len(results))

    # 4. Flush on shutdown
    client.flush()

When ``enabled=False`` (the default) all tracing primitives are
transparent no-ops with negligible overhead.
"""

from aurora_ext.observability.bridge import ObservabilityBridge
from aurora_ext.observability.config import LangfuseConfig, load_langfuse_config
from aurora_ext.observability.context import (
    TraceContext,
    nested_span,
    trace_generation,
    trace_span,
)
from aurora_ext.observability.decorators import (
    trace_embedding,
    trace_kg_extraction,
    trace_llm,
    trace_operation,
    trace_rag_query,
    trace_reranker,
)
from aurora_ext.observability.langfuse_client import (
    LangfuseClient,
    SpanHandle,
    TraceHandle,
    get_langfuse_client,
    reset_langfuse_client,
)

__all__ = [
    # Config
    "LangfuseConfig",
    "load_langfuse_config",
    # Client
    "LangfuseClient",
    "TraceHandle",
    "SpanHandle",
    "get_langfuse_client",
    "reset_langfuse_client",
    # Context managers
    "TraceContext",
    "trace_span",
    "trace_generation",
    "nested_span",
    # Decorators
    "trace_llm",
    "trace_embedding",
    "trace_kg_extraction",
    "trace_rag_query",
    "trace_reranker",
    "trace_operation",
    # Bridge
    "ObservabilityBridge",
]
