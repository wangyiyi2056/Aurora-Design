"""Tests for the health, metrics, and tracing API endpoints.

Uses a minimal FastAPI app with only the health + prometheus routers
to avoid the full application lifespan (which requires DuckDB etc.).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aurora_ext.rag.observability.metrics import MetricsCollector
from aurora_ext.rag.observability.tracing import TraceStore
from aurora_serve.health.api import router as health_router
from aurora_serve.health.api import prometheus_router
from aurora_serve.health.service import HealthService


def _build_test_app(
    *,
    llm_count: int = 1,
    embedding_count: int = 1,
    pipeline_busy: bool = False,
) -> FastAPI:
    """Build a minimal FastAPI app with health routes and mocked state."""
    app = FastAPI()

    # Mock model registry
    registry = MagicMock()
    registry._llms = {f"model_{i}": MagicMock() for i in range(llm_count)}
    registry._embeddings = {f"emb_{i}": MagicMock() for i in range(embedding_count)}
    app.state.model_registry = registry

    # Mock knowledge v2 service with pipeline
    from aurora_ext.rag.pipeline.status import PipelineManager, PipelineStatus
    from aurora_ext.rag.storage.json_kv import JsonKVStorage
    from aurora_ext.rag.storage.json_doc_status import JsonDocStatusStorage

    doc_status = MagicMock()
    pipeline_mgr = MagicMock()
    pipeline_status = PipelineStatus(busy=pipeline_busy)
    pipeline_mgr.status = pipeline_status
    pipeline_mgr.is_busy = pipeline_busy

    kv_storage = MagicMock()
    kv_storage.namespace = "test_kv"
    vector_storage = MagicMock()
    vector_storage.namespace = "test_vector"
    graph_storage = MagicMock()
    graph_storage.namespace = "test_graph"
    doc_status_storage = MagicMock()
    doc_status_storage.namespace = "test_doc_status"

    kb_service = MagicMock()
    kb_service._pipeline = pipeline_mgr
    kb_service._kv = kv_storage
    kb_service._vector = vector_storage
    kb_service._graph = graph_storage
    kb_service._doc_status = doc_status_storage
    app.state.knowledge_v2_service = kb_service

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(prometheus_router)

    return app


# ── Health Endpoints ──────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_check_returns_ok_when_all_healthy(self):
        app = _build_test_app(llm_count=1, embedding_count=1)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ok"
            assert "checks" in body
            assert "timestamp" in body

    def test_health_check_degraded_when_no_llm(self):
        app = _build_test_app(llm_count=0)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "degraded"

    def test_health_check_includes_storage_status(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            storage = body["checks"]["storage"]
            assert "status" in storage
            assert "backends" in storage
            for key in ("kv", "vector", "graph", "doc_status"):
                assert key in storage["backends"]
                assert storage["backends"][key]["status"] == "ok"

    def test_health_check_includes_pipeline_status(self):
        app = _build_test_app(pipeline_busy=False)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            pipeline = body["checks"]["pipeline"]
            assert pipeline["busy"] is False
            assert pipeline["status"] == "idle"

    def test_health_check_pipeline_busy(self):
        app = _build_test_app(pipeline_busy=True)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            pipeline = body["checks"]["pipeline"]
            assert pipeline["busy"] is True
            assert pipeline["status"] == "busy"

    def test_health_check_includes_model_status(self):
        app = _build_test_app(llm_count=2, embedding_count=1)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            models = body["checks"]["models"]
            assert models["llm_count"] == 2
            assert models["embedding_count"] == 1
            assert len(models["models"]) == 3

    def test_health_check_includes_system_info(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            system = body["checks"]["system"]
            assert "uptime_seconds" in system
            assert system["uptime_seconds"] >= 0
            assert "python_version" in system

    def test_health_summary_no_metrics_snapshot(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/summary")
            body = resp.json()
            assert "metrics_snapshot" not in body

    def test_health_detailed_includes_metrics_snapshot(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            body = resp.json()
            assert "metrics_snapshot" in body
            assert "counters" in body["metrics_snapshot"]


class TestReadinessProbe:
    def test_ready_when_llm_available(self):
        app = _build_test_app(llm_count=1)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/ready")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ready"] is True

    def test_not_ready_when_no_llm(self):
        app = _build_test_app(llm_count=0)
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/ready")
            assert resp.status_code == 503
            body = resp.json()
            assert body["ready"] is False
            assert len(body["reasons"]) > 0


class TestLivenessProbe:
    def test_always_alive(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/live")
            assert resp.status_code == 200
            assert resp.json()["alive"] is True


# ── Metrics Endpoints ─────────────────────────────────────────────────


class TestMetricsEndpoint:
    def test_metrics_json(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/metrics")
            assert resp.status_code == 200
            body = resp.json()
            assert "counters" in body
            assert "gauges" in body
            assert "histograms" in body
            assert "derived" in body
            assert "cache_hit_rate" in body["derived"]

    def test_prometheus_endpoint(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/metrics")
            assert resp.status_code == 200
            text = resp.text
            # Should contain at least the uptime gauge
            assert "uptime_seconds" in text
            assert "# TYPE uptime_seconds gauge" in text

    def test_prometheus_endpoint_content_type(self):
        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/metrics")
            assert "text/plain" in resp.headers["content-type"]


# ── Tracing Endpoints ─────────────────────────────────────────────────


class TestTracingEndpoints:
    def test_list_traces_empty(self):
        # Reset the trace store before testing
        from aurora_ext.rag.observability.tracing import get_trace_store
        get_trace_store().reset()

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces")
            assert resp.status_code == 200
            body = resp.json()
            assert "items" in body
            assert "total" in body
            assert body["total"] == 0

    def test_list_traces_with_data(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()
        store.create_trace("track_001", kb_name="kb_test", total_docs=5)

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces")
            body = resp.json()
            assert body["total"] >= 1
            assert body["items"][0]["track_id"] == "track_001"

    def test_list_traces_pagination(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()
        for i in range(5):
            t = store.create_trace(f"track_{i:03d}")
            t.finish()

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces?page=1&page_size=2")
            body = resp.json()
            assert len(body["items"]) == 2
            assert body["total"] == 5
            assert body["page"] == 1
            assert body["page_size"] == 2

    def test_list_traces_filter_by_status(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()
        t1 = store.create_trace("track_ok")
        t1.finish(status="completed")
        t2 = store.create_trace("track_fail")
        t2.finish(status="failed")

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces?status=completed")
            body = resp.json()
            assert body["total"] == 1
            assert body["items"][0]["track_id"] == "track_ok"

    def test_list_traces_filter_by_kb(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()
        store.create_trace("track_a", kb_name="kb_alpha")
        store.create_trace("track_b", kb_name="kb_beta")

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces?kb_name=kb_alpha")
            body = resp.json()
            assert body["total"] == 1

    def test_trace_stats(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert "total_traces" in body
            assert "by_status" in body
            assert "max_traces" in body

    def test_trace_detail_found(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        store = get_trace_store()
        store.reset()
        trace = store.create_trace("track_detail_test")
        trace.add_span(doc_id="d1", stage="parse").finish()
        trace.add_span(doc_id="d1", stage="extract").finish()

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces/track_detail_test")
            assert resp.status_code == 200
            body = resp.json()
            assert body["track_id"] == "track_detail_test"
            assert len(body["spans"]) == 2
            assert "stage_summary" in body

    def test_trace_detail_not_found(self):
        from aurora_ext.rag.observability.tracing import get_trace_store
        get_trace_store().reset()

        app = _build_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/traces/nonexistent")
            assert resp.status_code == 404
