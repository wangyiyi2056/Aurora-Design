"""Tests for LangfuseClient wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from aurora_ext.observability.config import LangfuseConfig
from aurora_ext.observability.langfuse_client import (
    LangfuseClient,
    SpanHandle,
    TraceHandle,
    _NoOpTrace,
    get_langfuse_client,
    reset_langfuse_client,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def disabled_config() -> LangfuseConfig:
    return LangfuseConfig(enabled=False)


@pytest.fixture
def enabled_config() -> LangfuseConfig:
    return LangfuseConfig(
        enabled=True,
        public_key="pk-test",
        secret_key="sk-test",
        host="https://test.langfuse.com",
    )


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton between tests."""
    yield
    reset_langfuse_client()


# ── NoOpTrace ────────────────────────────────────────────────────────


class TestNoOpTrace:
    """Tests for the _NoOpTrace stub."""

    def test_noop_trace_returns_self(self):
        noop = _NoOpTrace("trace-123")
        assert noop.span() is noop
        assert noop.generation() is noop
        assert noop.event() is noop

    def test_noop_trace_methods_do_not_raise(self):
        noop = _NoOpTrace("trace-123")
        noop.update(output="test")
        noop.end()
        noop.score(name="test", value=1.0)


# ── LangfuseClient (disabled mode) ──────────────────────────────────


class TestLangfuseClientDisabled:
    """Tests for the client in disabled mode."""

    def test_initialise_returns_false_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        assert client.initialise() is False
        assert client.is_enabled is False

    def test_initialise_returns_false_when_no_sdk(self, enabled_config):
        """When the SDK is not installed, initialise should return False."""
        client = LangfuseClient(enabled_config)
        # Mock ImportError
        with patch.dict("sys.modules", {"langfuse": None}):
            result = client.initialise()
        assert result is False
        assert client.is_enabled is False

    def test_flush_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        # Should not raise
        client.flush()

    def test_shutdown_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        client.shutdown()

    def test_start_trace_returns_handle_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        handle = client.start_trace(name="test-trace")
        assert isinstance(handle, TraceHandle)
        assert handle.name == "test-trace"
        assert len(handle.trace_id) == 16

    def test_end_trace_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        handle = client.start_trace(name="test")
        client.end_trace(handle, output="done")

    def test_start_span_returns_handle_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        span = client.start_span(trace, name="child-span")
        assert isinstance(span, SpanHandle)
        assert span.trace_id == trace.trace_id
        assert span.name == "child-span"

    def test_end_span_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        span = client.start_span(trace, name="child")
        client.end_span(span, output="result")

    def test_start_generation_returns_handle_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        gen = client.start_generation(trace, name="llm", model="gpt-4o")
        assert isinstance(gen, SpanHandle)

    def test_end_generation_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        gen = client.start_generation(trace, name="llm", model="gpt-4o")
        client.end_generation(
            gen,
            output="Hi",
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

    def test_record_event_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        client.record_event(trace, name="event", metadata={"key": "val"})

    def test_score_is_noop_when_disabled(self, disabled_config):
        client = LangfuseClient(disabled_config)
        trace = client.start_trace(name="test")
        client.score(trace, name="accuracy", value=0.95)


# ── LangfuseClient (enabled mode with mock SDK) ─────────────────────


class TestLangfuseClientEnabled:
    """Tests for the client with a mock Langfuse SDK."""

    @pytest.fixture
    def mock_langfuse_sdk(self):
        """Create a mock Langfuse SDK module."""
        mock_module = MagicMock()
        mock_instance = MagicMock()
        mock_module.Langfuse.return_value = mock_instance
        return mock_module, mock_instance

    @pytest.fixture
    def enabled_client(self, enabled_config, mock_langfuse_sdk):
        """Create an enabled client with mocked SDK."""
        mock_module, mock_instance = mock_langfuse_sdk
        with patch.dict("sys.modules", {"langfuse": mock_module}):
            client = LangfuseClient(enabled_config)
            client.initialise()
        yield client, mock_instance

    def test_initialise_loads_sdk(self, enabled_client):
        client, _ = enabled_client
        assert client.is_enabled is True

    def test_start_trace_calls_sdk(self, enabled_client):
        client, sdk = enabled_client
        handle = client.start_trace(
            name="test-trace",
            user_id="user-1",
            session_id="session-1",
            tags=["test"],
            metadata={"key": "value"},
        )
        sdk.trace.assert_called_once()
        call_kwargs = sdk.trace.call_args[1]
        assert call_kwargs["name"] == "test-trace"
        assert call_kwargs["user_id"] == "user-1"
        assert call_kwargs["session_id"] == "session-1"

    def test_start_trace_includes_default_tags(self, mock_langfuse_sdk):
        """Default tags from config should be merged with explicit tags."""
        config = LangfuseConfig(
            enabled=True,
            public_key="pk-test",
            secret_key="sk-test",
            default_tags=("aurora", "rag"),
        )
        mock_module, mock_instance = mock_langfuse_sdk
        with patch.dict("sys.modules", {"langfuse": mock_module}):
            client = LangfuseClient(config)
            client.initialise()

        handle = client.start_trace(name="test", tags=["extra"])
        call_kwargs = mock_instance.trace.call_args[1]
        assert "aurora" in call_kwargs["tags"]
        assert "rag" in call_kwargs["tags"]
        assert "extra" in call_kwargs["tags"]

    def test_start_generation_calls_sdk(self, enabled_client):
        client, sdk = enabled_client
        trace = client.start_trace(name="test")
        gen = client.start_generation(
            trace, name="llm", model="gpt-4o", input=[{"role": "user", "content": "hi"}]
        )
        sdk.generation.assert_called_once()

    def test_end_generation_with_usage(self, enabled_client):
        client, sdk = enabled_client
        trace = client.start_trace(name="test")
        gen = client.start_generation(trace, name="llm", model="gpt-4o")
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        client.end_generation(gen, output="response", model="gpt-4o", usage=usage)
        # Should have been called twice: start + end
        assert sdk.generation.call_count == 2

    def test_flush_calls_sdk(self, enabled_client):
        client, sdk = enabled_client
        client.flush()
        sdk.flush.assert_called_once()

    def test_shutdown_flushes_and_closes(self, enabled_client):
        client, sdk = enabled_client
        client.shutdown()
        sdk.flush.assert_called_once()
        sdk.shutdown.assert_called_once()
        assert client.is_enabled is False

    def test_sdk_exception_does_not_crash(self, enabled_client):
        """SDK failures should be logged but not raised."""
        client, sdk = enabled_client
        sdk.trace.side_effect = RuntimeError("Network error")
        # Should not raise
        handle = client.start_trace(name="test")
        assert isinstance(handle, TraceHandle)

    def test_record_event_calls_sdk(self, enabled_client):
        client, sdk = enabled_client
        trace = client.start_trace(name="test")
        client.record_event(trace, name="custom_event", metadata={"foo": "bar"})
        sdk.event.assert_called_once()

    def test_score_calls_sdk(self, enabled_client):
        client, sdk = enabled_client
        trace = client.start_trace(name="test")
        client.score(trace, name="accuracy", value=0.95, comment="good")
        sdk.score.assert_called_once()


# ── Singleton management ─────────────────────────────────────────────


class TestSingleton:
    """Tests for get_langfuse_client / reset_langfuse_client."""

    def test_get_returns_same_instance(self):
        config = LangfuseConfig()
        client1 = get_langfuse_client(config)
        client2 = get_langfuse_client(config)
        assert client1 is client2

    def test_reset_clears_singleton(self):
        config = LangfuseConfig()
        client1 = get_langfuse_client(config)
        reset_langfuse_client()
        client2 = get_langfuse_client(config)
        assert client1 is not client2

    def test_get_with_default_config(self):
        """Calling without config should use load_langfuse_config."""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}, clear=True):
            client = get_langfuse_client()
        assert isinstance(client, LangfuseClient)
        assert client.config.enabled is False
