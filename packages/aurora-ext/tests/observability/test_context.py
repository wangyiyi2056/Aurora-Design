"""Tests for trace context managers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aurora_ext.observability.config import LangfuseConfig
from aurora_ext.observability.context import (
    TraceContext,
    nested_span,
    trace_generation,
    trace_span,
)
from aurora_ext.observability.langfuse_client import LangfuseClient, reset_langfuse_client


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset():
    yield
    reset_langfuse_client()


@pytest.fixture
def disabled_client() -> LangfuseClient:
    config = LangfuseConfig(enabled=False)
    return LangfuseClient(config)


@pytest.fixture
def mock_enabled_client() -> tuple[LangfuseClient, MagicMock]:
    config = LangfuseConfig(
        enabled=True, public_key="pk-test", secret_key="sk-test"
    )
    client = LangfuseClient(config)
    mock_sdk = MagicMock()
    client._langfuse = mock_sdk
    client._initialised = True
    return client, mock_sdk


# ── TraceContext ─────────────────────────────────────────────────────


class TestTraceContext:
    """Tests for the TraceContext dataclass."""

    def test_elapsed_time(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        assert ctx.elapsed_seconds >= 0
        assert ctx.elapsed_ms >= 0

    def test_add_metadata(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        ctx.add_metadata("key1", "value1")
        ctx.add_metadata("key2", 42)
        assert ctx._metadata == {"key1": "value1", "key2": 42}

    def test_set_output(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        ctx.set_output("hello world")
        assert ctx._output == "hello world"

    def test_set_error(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        ctx.set_error("something went wrong")
        assert ctx._error == "something went wrong"

    def test_set_usage(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        ctx.set_usage(prompt_tokens=10, completion_tokens=5)
        assert ctx._usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_set_usage_explicit_total(self, disabled_client):
        from aurora_ext.observability.langfuse_client import TraceHandle

        handle = TraceHandle(trace_id="t1", name="test")
        ctx = TraceContext(
            trace_id="t1",
            name="test",
            _client=disabled_client,
            _trace_handle=handle,
        )
        ctx.set_usage(prompt_tokens=10, completion_tokens=5, total_tokens=20)
        assert ctx._usage["total_tokens"] == 20


# ── trace_span ───────────────────────────────────────────────────────


class TestTraceSpan:
    """Tests for the trace_span context manager."""

    def test_basic_usage_disabled(self, disabled_client):
        with trace_span("test-span", client=disabled_client) as ctx:
            assert ctx.name == "test-span"
            assert ctx.trace_id
            ctx.add_metadata("key", "value")
            ctx.set_output("result")

    def test_records_error_on_exception(self, disabled_client):
        with pytest.raises(ValueError, match="test error"):
            with trace_span("test-span", client=disabled_client) as ctx:
                raise ValueError("test error")

        assert "ValueError" in ctx._error
        assert "test error" in ctx._error

    def test_metadata_preserved(self, disabled_client):
        with trace_span(
            "test", metadata={"initial": "meta"}, client=disabled_client
        ) as ctx:
            ctx.add_metadata("added", "later")
            assert ctx._metadata["initial"] == "meta"
            assert ctx._metadata["added"] == "later"

    def test_user_and_session_id(self, disabled_client):
        with trace_span(
            "test",
            user_id="user-123",
            session_id="session-456",
            client=disabled_client,
        ) as ctx:
            assert ctx.name == "test"

    def test_tags_passed_through(self, disabled_client):
        with trace_span(
            "test",
            tags=["tag1", "tag2"],
            client=disabled_client,
        ) as ctx:
            assert ctx.name == "test"

    def test_enabled_calls_sdk(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        with trace_span("test-span", client=client) as ctx:
            ctx.set_output("done")

        sdk.trace.assert_called_once()

    def test_enabled_calls_end_trace(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        with trace_span("test-span", client=client):
            pass

        # get_trace is called by end_trace
        sdk.get_trace.assert_called_once()


# ── trace_generation ─────────────────────────────────────────────────


class TestTraceGeneration:
    """Tests for the trace_generation context manager."""

    def test_basic_usage_disabled(self, disabled_client):
        with trace_generation(
            "llm-call", model="gpt-4o", client=disabled_client
        ) as ctx:
            ctx.set_output("Hello!")
            ctx.set_usage(prompt_tokens=5, completion_tokens=3)

        assert ctx._output == "Hello!"
        assert ctx._usage["prompt_tokens"] == 5

    def test_records_error_on_exception(self, disabled_client):
        with pytest.raises(RuntimeError):
            with trace_generation("llm-call", client=disabled_client) as ctx:
                raise RuntimeError("API error")

        assert "RuntimeError" in ctx._error

    def test_enabled_creates_generation(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        with trace_generation(
            "llm-call",
            model="gpt-4o",
            input=[{"role": "user", "content": "hi"}],
            client=client,
        ) as ctx:
            ctx.set_output("response")
            ctx.set_usage(prompt_tokens=10, completion_tokens=5)

        # trace + generation start + generation end
        sdk.trace.assert_called_once()
        assert sdk.generation.call_count == 2

    def test_input_preserved(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        messages = [{"role": "user", "content": "hello"}]
        with trace_generation(
            "llm-call", model="gpt-4o", input=messages, client=client
        ) as ctx:
            pass

        gen_call = sdk.generation.call_args_list[0]
        assert gen_call[1]["input"] == messages


# ── nested_span ──────────────────────────────────────────────────────


class TestNestedSpan:
    """Tests for the nested_span context manager."""

    def test_basic_nested_usage(self, disabled_client):
        with trace_span("parent", client=disabled_client) as parent_ctx:
            with nested_span(parent_ctx, "child-op") as child_ctx:
                child_ctx.set_output("child result")
                child_ctx.add_metadata("step", 1)

        assert child_ctx._output == "child result"
        assert child_ctx.trace_id == parent_ctx.trace_id

    def test_nested_error_propagation(self, disabled_client):
        with pytest.raises(ValueError):
            with trace_span("parent", client=disabled_client) as parent_ctx:
                with nested_span(parent_ctx, "child-op") as child_ctx:
                    raise ValueError("child error")

        assert "ValueError" in child_ctx._error

    def test_deeply_nested_spans(self, disabled_client):
        with trace_span("root", client=disabled_client) as root:
            with nested_span(root, "level-1") as l1:
                with nested_span(l1, "level-2") as l2:
                    l2.set_output("deep result")

        assert l2.trace_id == root.trace_id

    def test_nested_with_enabled_client(self, mock_enabled_client):
        client, sdk = mock_enabled_client

        with trace_span("parent", client=client) as parent_ctx:
            with nested_span(parent_ctx, "child") as child_ctx:
                child_ctx.set_output("result")

        # start_span for child + end_span for child
        assert sdk.span.call_count >= 2
