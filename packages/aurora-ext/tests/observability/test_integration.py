"""Integration tests — end-to-end tracing workflows."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aurora_ext.observability import (
    LangfuseConfig,
    LangfuseClient,
    ObservabilityBridge,
    TraceContext,
    load_langfuse_config,
    nested_span,
    reset_langfuse_client,
    trace_embedding,
    trace_generation,
    trace_kg_extraction,
    trace_llm,
    trace_operation,
    trace_rag_query,
    trace_reranker,
    trace_span,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset():
    yield
    reset_langfuse_client()


@pytest.fixture
def mock_sdk():
    """A mock Langfuse SDK module."""
    mock_module = MagicMock()
    mock_instance = MagicMock()
    mock_module.Langfuse.return_value = mock_instance
    return mock_module, mock_instance


@pytest.fixture
def enabled_client(mock_sdk) -> tuple[LangfuseClient, MagicMock]:
    config = LangfuseConfig(
        enabled=True,
        public_key="pk-integration-test",
        secret_key="sk-integration-test",
        project_name="Integration Tests",
        default_tags=("test",),
    )
    mock_module, mock_instance = mock_sdk

    import sys

    sys.modules["langfuse"] = mock_module
    try:
        client = LangfuseClient(config)
        client.initialise()
        yield client, mock_instance
    finally:
        sys.modules.pop("langfuse", None)


# ── End-to-end workflows ─────────────────────────────────────────────


class TestEndToEndRAGQueryWorkflow:
    """Simulate a complete RAG query with tracing."""

    def test_full_query_pipeline(self, enabled_client):
        """Trace a full RAG query: keywords → retrieval → rerank → generate."""
        client, sdk = enabled_client

        @trace_rag_query(client=client)
        def execute_query(query: str, mode: str = "mix"):
            return {
                "response": "The answer is 42.",
                "entities": ["Entity1"],
                "chunks": [{"id": "c1", "score": 0.95}],
            }

        result = execute_query("What is the answer?", mode="mix")
        assert result["response"] == "The answer is 42."

        # Verify trace was created
        sdk.trace.assert_called()

    def test_full_query_with_nested_operations(self, enabled_client):
        """Nested spans within a query trace."""
        client, sdk = enabled_client

        with trace_span("rag-query", client=client) as ctx:
            ctx.add_metadata("query", "What is Python?")
            ctx.add_metadata("mode", "mix")

            with nested_span(ctx, "keyword-extraction") as kw_ctx:
                kw_ctx.set_output({"hl": ["Python"], "ll": ["python"]})

            with nested_span(ctx, "vector-retrieval") as ret_ctx:
                ret_ctx.set_output({"chunks_found": 10})

            with nested_span(ctx, "reranking") as rerank_ctx:
                rerank_ctx.set_output({"chunks_reranked": 10})

            with nested_span(ctx, "response-generation") as gen_ctx:
                gen_ctx.set_output("Python is a programming language.")

            ctx.set_output("Python is a programming language.")

        # Verify: 1 trace + 4 nested spans (start + end each)
        sdk.trace.assert_called()
        assert sdk.span.call_count >= 8  # 4 start + 4 end


class TestEndToEndKGExtraction:
    """Simulate KG extraction tracing."""

    def test_extraction_pipeline(self, enabled_client):
        client, sdk = enabled_client

        @trace_kg_extraction(client=client)
        def extract_from_chunk(chunk_text: str, chunk_id: str):
            return {
                "entities": [
                    {"name": "Python", "type": "Technology"},
                    {"name": "Guido", "type": "Person"},
                ],
                "relationships": [
                    {"source": "Guido", "target": "Python", "type": "created"},
                ],
            }

        result = extract_from_chunk("Guido created Python.", "chunk-001")
        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 1

        # Verify trace
        sdk.trace.assert_called()


class TestEndToEndEmbedding:
    """Simulate embedding call tracing."""

    def test_embedding_call(self, enabled_client):
        client, sdk = enabled_client

        @trace_embedding(client=client)
        def compute_embeddings(texts: list[str]):
            return [[0.1, 0.2, 0.3] for _ in texts]

        result = compute_embeddings(["hello", "world"])
        assert len(result) == 2

        sdk.trace.assert_called()


class TestEndToEndReranker:
    """Simulate reranker tracing."""

    def test_reranker_call(self, enabled_client):
        client, sdk = enabled_client

        @trace_reranker(client=client)
        def rerank_docs(query: str, docs: list[str], top_n: int = 3):
            return [
                {"index": 2, "score": 0.95},
                {"index": 0, "score": 0.85},
                {"index": 1, "score": 0.72},
            ]

        result = rerank_docs("query", ["doc1", "doc2", "doc3"])
        assert len(result) == 3
        assert result[0]["score"] == 0.95

        sdk.trace.assert_called()


class TestEndToEndLLMCall:
    """Simulate LLM call tracing with generation observation."""

    def test_llm_call_with_generation(self, enabled_client):
        client, sdk = enabled_client

        with trace_generation(
            "llm-chat",
            model="gpt-4o",
            input=[{"role": "user", "content": "Hello"}],
            client=client,
        ) as ctx:
            # Simulate LLM response
            ctx.set_output("Hello! How can I help?")
            ctx.set_usage(prompt_tokens=10, completion_tokens=8)

        assert ctx._output == "Hello! How can I help?"
        assert ctx._usage["total_tokens"] == 18

        # Verify generation was created
        sdk.trace.assert_called()
        assert sdk.generation.call_count == 2  # start + end


class TestBridgeIntegration:
    """Integration tests for the ObservabilityBridge."""

    def test_forward_pipeline_trace_to_langfuse(self, enabled_client):
        client, sdk = enabled_client
        bridge = ObservabilityBridge(client)

        # Simulate a pipeline trace from TraceStore
        pipeline_trace = {
            "track_id": "pipeline-001",
            "kb_name": "default",
            "status": "completed",
            "total_docs": 10,
            "processed_docs": 9,
            "failed_docs": 1,
            "duration_ms": 5432.1,
            "spans": [
                {
                    "stage": "parse",
                    "doc_id": "doc-001",
                    "status": "completed",
                    "duration_ms": 200,
                    "error_message": "",
                    "metadata": {"parser": "pdf"},
                },
                {
                    "stage": "chunk",
                    "doc_id": "doc-001",
                    "status": "completed",
                    "duration_ms": 50,
                    "error_message": "",
                    "metadata": {"chunks": 15},
                },
                {
                    "stage": "extract",
                    "doc_id": "doc-001",
                    "status": "completed",
                    "duration_ms": 3000,
                    "error_message": "",
                    "metadata": {"entities": 5, "relations": 3},
                },
                {
                    "stage": "embed",
                    "doc_id": "doc-001",
                    "status": "completed",
                    "duration_ms": 500,
                    "error_message": "",
                    "metadata": {},
                },
            ],
        }

        bridge.forward_trace(pipeline_trace)

        # Verify: 1 trace + 4 span starts
        sdk.trace.assert_called_once()
        assert sdk.span.call_count == 4
        # Score for completed
        sdk.score.assert_called_once()

    def test_forward_llm_metric_event(self, enabled_client):
        client, sdk = enabled_client
        bridge = ObservabilityBridge(client)

        bridge.forward_metric_event(
            "llm_call",
            model="gpt-4o-mini",
            input_tokens=500,
            output_tokens=200,
            duration_seconds=1.5,
            success=True,
        )

        sdk.trace.assert_called_once()
        assert sdk.generation.call_count == 2  # start + end


class TestConfigIntegration:
    """Test configuration loading from multiple sources."""

    def test_full_config_round_trip(self):
        """Load config, create client, verify settings."""
        import os
        from unittest.mock import patch

        env = {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-12345678",
            "LANGFUSE_SECRET_KEY": "sk-lf-87654321",
            "LANGFUSE_HOST": "https://cloud.langfuse.com",
            "LANGFUSE_PROJECT_NAME": "Aurora Production",
            "LANGFUSE_SAMPLE_RATE": "0.8",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_langfuse_config()

        assert config.is_configured is True
        assert config.public_key == "pk-lf-12345678"
        assert config.project_name == "Aurora Production"
        assert config.sample_rate == 0.8
        assert config.host == "https://cloud.langfuse.com"

    def test_disabled_by_default(self):
        """Without any config, tracing should be disabled."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            config = load_langfuse_config()

        assert config.enabled is False
        assert config.is_configured is False
