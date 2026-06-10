"""Tests for ObservabilityBridge."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aurora_ext.observability.bridge import ObservabilityBridge
from aurora_ext.observability.config import LangfuseConfig
from aurora_ext.observability.langfuse_client import LangfuseClient, reset_langfuse_client


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset():
    yield
    reset_langfuse_client()


@pytest.fixture
def disabled_bridge() -> ObservabilityBridge:
    config = LangfuseConfig(enabled=False)
    client = LangfuseClient(config)
    return ObservabilityBridge(client)


@pytest.fixture
def mock_enabled_bridge() -> tuple[ObservabilityBridge, MagicMock]:
    config = LangfuseConfig(
        enabled=True, public_key="pk-test", secret_key="sk-test"
    )
    client = LangfuseClient(config)
    mock_sdk = MagicMock()
    client._langfuse = mock_sdk
    client._initialised = True
    return ObservabilityBridge(client), mock_sdk


# ── Lifecycle ────────────────────────────────────────────────────────


class TestBridgeLifecycle:
    """Tests for bridge lifecycle methods."""

    def test_is_enabled_false_when_disabled(self, disabled_bridge):
        assert disabled_bridge.is_enabled is False

    def test_flush_noop_when_disabled(self, disabled_bridge):
        # Should not raise
        disabled_bridge.flush()

    def test_shutdown_noop_when_disabled(self, disabled_bridge):
        disabled_bridge.shutdown()


# ── Trace forwarding ─────────────────────────────────────────────────


class TestForwardTrace:
    """Tests for forward_trace."""

    def test_noop_when_none(self, disabled_bridge):
        # Should not raise
        disabled_bridge.forward_trace(None)

    def test_noop_when_disabled(self, disabled_bridge):
        detail = {
            "track_id": "track-123",
            "kb_name": "default",
            "status": "completed",
            "spans": [],
        }
        disabled_bridge.forward_trace(detail)

    def test_creates_trace_when_enabled(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        detail = {
            "track_id": "track-123",
            "kb_name": "default",
            "status": "completed",
            "total_docs": 5,
            "processed_docs": 5,
            "failed_docs": 0,
            "duration_ms": 1234.5,
            "spans": [],
        }
        bridge.forward_trace(detail)
        sdk.trace.assert_called_once()

    def test_forwards_spans_as_observations(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        detail = {
            "track_id": "track-123",
            "kb_name": "default",
            "status": "completed",
            "spans": [
                {
                    "stage": "parse",
                    "doc_id": "doc-1",
                    "status": "completed",
                    "duration_ms": 100,
                    "error_message": "",
                    "metadata": {},
                },
                {
                    "stage": "embed",
                    "doc_id": "doc-1",
                    "status": "completed",
                    "duration_ms": 200,
                    "error_message": "",
                    "metadata": {},
                },
            ],
        }
        bridge.forward_trace(detail)
        # 2 spans
        assert sdk.span.call_count == 2

    def test_scores_completed_trace(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        detail = {
            "track_id": "track-123",
            "status": "completed",
            "spans": [],
        }
        bridge.forward_trace(detail)
        sdk.score.assert_called_once()
        call_kwargs = sdk.score.call_args[1]
        assert call_kwargs["value"] == "completed"

    def test_scores_failed_trace(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        detail = {
            "track_id": "track-123",
            "status": "failed",
            "spans": [],
        }
        bridge.forward_trace(detail)
        sdk.score.assert_called_once()
        call_kwargs = sdk.score.call_args[1]
        assert call_kwargs["value"] == "failed"

    def test_includes_kb_tag(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        detail = {
            "track_id": "track-123",
            "kb_name": "my-kb",
            "status": "completed",
            "spans": [],
        }
        bridge.forward_trace(detail)
        call_kwargs = sdk.trace.call_args[1]
        assert "kb:my-kb" in call_kwargs["tags"]


# ── Metric event forwarding ─────────────────────────────────────────


class TestForwardMetricEvent:
    """Tests for forward_metric_event."""

    def test_noop_when_disabled(self, disabled_bridge):
        disabled_bridge.forward_metric_event(
            "llm_call", model="gpt-4o", duration_seconds=1.5
        )

    def test_llm_call_creates_generation(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        bridge.forward_metric_event(
            "llm_call",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            duration_seconds=2.5,
        )
        sdk.trace.assert_called_once()
        assert sdk.generation.call_count == 2  # start + end

    def test_embedding_call_creates_span(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        bridge.forward_metric_event(
            "embedding_call",
            model="text-embedding-ada-002",
            token_count=500,
            duration_seconds=0.5,
        )
        sdk.trace.assert_called_once()
        sdk.span.assert_called()

    def test_cache_result_creates_span(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        bridge.forward_metric_event(
            "cache_result",
            duration_seconds=0.001,
            success=True,
        )
        sdk.trace.assert_called_once()

    def test_includes_model_tag(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge
        bridge.forward_metric_event(
            "llm_call",
            model="gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
        )
        call_kwargs = sdk.trace.call_args[1]
        assert "model:gpt-4o-mini" in call_kwargs["tags"]


# ── Bulk sync ────────────────────────────────────────────────────────


class TestSyncAllTraces:
    """Tests for sync_all_traces."""

    def test_returns_zero_when_disabled(self, disabled_bridge):
        mock_store = MagicMock()
        count = disabled_bridge.sync_all_traces(mock_store)
        assert count == 0

    def test_syncs_all_traces(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge

        mock_store = MagicMock()
        mock_store.list_traces.side_effect = [
            (
                [
                    {"track_id": "t1"},
                    {"track_id": "t2"},
                ],
                2,
            ),
        ]
        mock_store.get_trace_detail.side_effect = [
            {"track_id": "t1", "status": "completed", "spans": []},
            {"track_id": "t2", "status": "completed", "spans": []},
        ]

        count = bridge.sync_all_traces(mock_store)
        assert count == 2

    def test_handles_empty_store(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge

        mock_store = MagicMock()
        mock_store.list_traces.return_value = ([], 0)

        count = bridge.sync_all_traces(mock_store)
        assert count == 0

    def test_respects_status_filter(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge

        mock_store = MagicMock()
        mock_store.list_traces.return_value = ([], 0)

        bridge.sync_all_traces(mock_store, status_filter="completed")
        mock_store.list_traces.assert_called_once_with(
            page=1, page_size=50, status="completed"
        )

    def test_handles_missing_detail(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge

        mock_store = MagicMock()
        mock_store.list_traces.return_value = (
            [{"track_id": "t1"}],
            1,
        )
        mock_store.get_trace_detail.return_value = None

        count = bridge.sync_all_traces(mock_store)
        assert count == 0

    def test_pagination(self, mock_enabled_bridge):
        bridge, sdk = mock_enabled_bridge

        mock_store = MagicMock()
        # With default page_size=50, 55 items needs 2 pages
        # Page 1: 50 results (track_ids t1..t50), total 55
        # Page 2: 5 results (track_ids t51..t55)
        page1 = [{"track_id": f"t{i}"} for i in range(1, 51)]
        page2 = [{"track_id": f"t{i}"} for i in range(51, 56)]
        mock_store.list_traces.side_effect = [
            (page1, 55),
            (page2, 55),
        ]

        # Provide trace details for all 55 traces
        details = []
        for i in range(1, 56):
            details.append({"track_id": f"t{i}", "status": "completed", "spans": []})
        mock_store.get_trace_detail.side_effect = details

        count = bridge.sync_all_traces(mock_store)
        assert count == 55
        assert mock_store.list_traces.call_count == 2
