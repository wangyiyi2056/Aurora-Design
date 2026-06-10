"""Tests for tracing decorators."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aurora_ext.observability.config import LangfuseConfig
from aurora_ext.observability.decorators import (
    _extract_usage,
    _safe_repr,
    trace_embedding,
    trace_kg_extraction,
    trace_llm,
    trace_operation,
    trace_rag_query,
    trace_reranker,
)
from aurora_ext.observability.langfuse_client import LangfuseClient, reset_langfuse_client


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset():
    yield
    reset_langfuse_client()


@pytest.fixture
def disabled_client() -> LangfuseClient:
    """Client in disabled mode (no-op)."""
    config = LangfuseConfig(enabled=False)
    return LangfuseClient(config)


@pytest.fixture
def mock_enabled_client() -> tuple[LangfuseClient, MagicMock]:
    """Client with mocked SDK that reports as enabled."""
    config = LangfuseConfig(
        enabled=True, public_key="pk-test", secret_key="sk-test"
    )
    client = LangfuseClient(config)
    mock_sdk = MagicMock()
    client._langfuse = mock_sdk
    client._initialised = True
    return client, mock_sdk


# ── Helper functions ─────────────────────────────────────────────────


class TestSafeRepr:
    """Tests for _safe_repr helper."""

    def test_none(self):
        assert _safe_repr(None) is None

    def test_primitives(self):
        assert _safe_repr(42) == 42
        assert _safe_repr(3.14) == 3.14
        assert _safe_repr(True) is True
        assert _safe_repr("hello") == "hello"

    def test_long_string_truncated(self):
        long_str = "a" * 1000
        result = _safe_repr(long_str, max_len=100)
        assert result.endswith("...")
        assert len(result) == 103  # 100 + "..."

    def test_small_list(self):
        result = _safe_repr([1, 2, 3])
        assert result == [1, 2, 3]

    def test_large_list(self):
        result = _safe_repr(list(range(20)))
        assert "len=20" in result

    def test_dict(self):
        result = _safe_repr({"key": "value"})
        assert result == {"key": "value"}

    def test_object(self):
        class Foo:
            pass

        result = _safe_repr(Foo())
        assert "<Foo>" in result


class TestExtractUsage:
    """Tests for _extract_usage helper."""

    def test_none(self):
        assert _extract_usage(None) is None

    def test_dict_with_usage(self):
        result = _extract_usage({
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        })
        assert result == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_dict_without_usage(self):
        assert _extract_usage({"text": "hello"}) is None

    def test_object_with_usage_dict(self):
        class Result:
            usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        result = _extract_usage(Result())
        assert result["prompt_tokens"] == 10

    def test_object_with_token_attributes(self):
        class Result:
            prompt_tokens = 10
            completion_tokens = 5

        result = _extract_usage(Result())
        assert result["prompt_tokens"] == 10
        assert result["completion_tokens"] == 5
        assert result["total_tokens"] == 15


# ── Decorator tests (disabled mode — pass-through) ───────────────────


class TestDecoratorsDisabled:
    """When disabled, decorators should be transparent pass-throughs."""

    def test_trace_llm_passthrough_sync(self, disabled_client):
        @trace_llm(client=disabled_client)
        def my_func(messages, model="gpt-4o"):
            return {"text": "hello"}

        result = my_func([{"role": "user", "content": "hi"}], model="gpt-4o")
        assert result == {"text": "hello"}

    def test_trace_llm_passthrough_async(self, disabled_client):
        @trace_llm(client=disabled_client)
        async def my_func(messages, model="gpt-4o"):
            return {"text": "hello"}

        result = asyncio.get_event_loop().run_until_complete(
            my_func([{"role": "user", "content": "hi"}])
        )
        assert result == {"text": "hello"}

    def test_trace_embedding_passthrough(self, disabled_client):
        @trace_embedding(client=disabled_client)
        def embed(texts):
            return [[0.1, 0.2, 0.3]]

        result = embed(["hello world"])
        assert result == [[0.1, 0.2, 0.3]]

    def test_trace_kg_extraction_passthrough(self, disabled_client):
        @trace_kg_extraction(client=disabled_client)
        def extract(text):
            return {"entities": [], "relations": []}

        result = extract("some text")
        assert result == {"entities": [], "relations": []}

    def test_trace_rag_query_passthrough(self, disabled_client):
        @trace_rag_query(client=disabled_client)
        async def query(q, mode="mix"):
            return "answer"

        result = asyncio.get_event_loop().run_until_complete(query("question"))
        assert result == "answer"

    def test_trace_reranker_passthrough(self, disabled_client):
        @trace_reranker(client=disabled_client)
        def rerank(query, docs, top_n=5):
            return [{"index": 0, "score": 0.9}]

        result = rerank("q", ["d1", "d2"])
        assert len(result) == 1

    def test_trace_operation_passthrough(self, disabled_client):
        @trace_operation("my-op", client=disabled_client)
        def op():
            return 42

        assert op() == 42

    def test_trace_llm_preserves_exception(self, disabled_client):
        @trace_llm(client=disabled_client)
        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fail()

    def test_trace_llm_preserves_exception_async(self, disabled_client):
        @trace_llm(client=disabled_client)
        async def fail():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            asyncio.get_event_loop().run_until_complete(fail())


# ── Decorator tests (enabled mode with mock SDK) ─────────────────────


class TestDecoratorsEnabled:
    """When enabled, decorators should create traces."""

    def test_trace_llm_creates_trace(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        @trace_llm(client=client)
        def call_llm(messages, model="gpt-4o"):
            return {
                "text": "response",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

        result = call_llm([{"role": "user", "content": "hi"}], model="gpt-4o")
        assert result["text"] == "response"
        sdk.trace.assert_called_once()
        assert sdk.generation.call_count == 2  # start + end

    def test_trace_llm_async_creates_trace(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        @trace_llm(client=client)
        async def call_llm(messages, model="gpt-4o"):
            return {"text": "async response"}

        result = asyncio.get_event_loop().run_until_complete(
            call_llm([], model="gpt-4o")
        )
        assert result["text"] == "async response"
        sdk.trace.assert_called_once()

    def test_trace_rag_query_creates_span(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        @trace_rag_query(client=client)
        def query(q, mode="mix"):
            return "answer"

        result = query("question", mode="mix")
        assert result == "answer"
        sdk.trace.assert_called_once()
        sdk.span.assert_called()

    def test_trace_llm_records_error_on_exception(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        @trace_llm(client=client)
        def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            fail()

        # Should have recorded the error event
        sdk.event.assert_called_once()

    def test_trace_operation_with_custom_name(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        @trace_operation("custom-op", trace_type="ingestion", client=client)
        def ingest():
            return {"docs": 5}

        result = ingest()
        assert result == {"docs": 5}
        call_kwargs = sdk.trace.call_args[1]
        assert call_kwargs["name"] == "custom-op"

    def test_decorator_preserves_function_metadata(self, disabled_client):
        @trace_llm(client=disabled_client)
        def my_special_function():
            """My docstring."""
            pass

        assert my_special_function.__name__ == "my_special_function"
        assert my_special_function.__doc__ == "My docstring."

    def test_decorator_without_parentheses(self, disabled_client):
        """@trace_llm (no parens) should work the same as @trace_llm()."""

        @trace_llm
        def func():
            return "ok"

        # In disabled mode with default singleton client
        assert func() == "ok"
