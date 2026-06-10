"""Health, metrics, and tracing API endpoints.

Routes
------
GET  /health            — Detailed health report
GET  /health/ready      — Readiness probe (k8s)
GET  /health/live       — Liveness probe (k8s)
GET  /health/metrics    — Internal metrics (JSON)
GET  /metrics           — Prometheus text exposition
GET  /health/traces     — Pipeline trace listing (paginated, filterable)
GET  /health/traces/stats — Trace store summary
GET  /health/traces/{track_id} — Single trace detail with spans
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from aurora_ext.rag.observability.metrics import get_metrics
from aurora_ext.rag.observability.tracing import get_trace_store
from aurora_serve.health.service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def _get_health_service(request: Request) -> HealthService:
    """Build or retrieve the HealthService, caching on app.state."""
    service = getattr(request.app.state, "health_service", None)
    if service is None:
        service = HealthService(request.app)
        request.app.state.health_service = service
    return service


# ── Health Endpoints ──────────────────────────────────────────────────


@router.get("")
async def health_check(request: Request):
    """Detailed health report with subsystem checks."""
    service = _get_health_service(request)
    report = await service.get_health(detailed=True)
    status_code = 200 if report["status"] == "ok" else 503
    # FastAPI will use 200 by default for dict returns; we use
    # JSONResponse to control status code explicitly.
    from fastapi.responses import JSONResponse
    return JSONResponse(content=report, status_code=status_code)


@router.get("/summary")
async def health_summary(request: Request):
    """Lightweight health check for load balancers."""
    service = _get_health_service(request)
    report = await service.get_health(detailed=False)
    return report


@router.get("/ready")
async def readiness_probe(request: Request):
    """Kubernetes readiness probe."""
    service = _get_health_service(request)
    result = await service.get_readiness()
    from fastapi.responses import JSONResponse
    status_code = 200 if result["ready"] else 503
    return JSONResponse(content=result, status_code=status_code)


@router.get("/live")
async def liveness_probe(request: Request):
    """Kubernetes liveness probe."""
    service = _get_health_service(request)
    return await service.get_liveness()


# ── Metrics Endpoints ─────────────────────────────────────────────────


@router.get("/metrics")
async def metrics_json():
    """Internal metrics as JSON."""
    metrics = get_metrics()
    return metrics.snapshot()


@router.get("/metrics/reset", include_in_schema=False)
async def metrics_reset():
    """Reset all metrics (development only)."""
    get_metrics().reset()
    return {"reset": True}


# ── Prometheus Endpoint (mounted at /metrics, not /health/metrics) ────

prometheus_router = APIRouter(tags=["observability"])


@prometheus_router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus text exposition format.

    Mount this at the top-level ``/metrics`` path (outside ``/api/v1``)
    for Prometheus scraper compatibility.
    """
    metrics = get_metrics()
    return metrics.export_prometheus()


# ── Tracing Endpoints ─────────────────────────────────────────────────


@router.get("/traces")
async def list_traces(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    kb_name: str | None = Query(None, description="Filter by knowledge base"),
):
    """List pipeline traces with pagination and filtering."""
    store = get_trace_store()
    traces, total = store.list_traces(
        page=page, page_size=page_size, status=status, kb_name=kb_name
    )
    return {
        "items": traces,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/traces/stats")
async def trace_stats():
    """Trace store summary statistics."""
    store = get_trace_store()
    return store.stats()


@router.get("/traces/{track_id}")
async def get_trace_detail(track_id: str):
    """Get full trace detail including all spans for a track_id."""
    store = get_trace_store()
    detail = store.get_trace_detail(track_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trace with track_id '{track_id}' not found",
        )
    return detail
