"""Health check service — aggregates subsystem status into a single report.

Queries storage backends, pipeline state, and model registry to produce
a comprehensive health snapshot consumed by the ``/health`` API.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aurora_core.component import BaseService
from aurora_ext.rag.observability.metrics import get_metrics

logger = logging.getLogger(__name__)


class HealthService(BaseService):
    """Aggregates health information from all Aurora subsystems."""

    name = "health_service"

    def __init__(self, app: Any) -> None:
        self._app = app
        self._start_time = time.time()

    async def get_health(self, *, detailed: bool = False) -> dict[str, Any]:
        """Build a complete health report.

        Parameters
        ----------
        detailed:
            When ``True``, includes storage backend probes and per-model
            status.  When ``False``, returns a lightweight summary suitable
            for load-balancer health probes.
        """
        metrics = get_metrics()
        metrics.inc("health_checks_total")

        # Overall status — degraded if any critical subsystem is down
        overall_status = "ok"
        checks: dict[str, Any] = {}

        # ── Storage Backends ────────────────────────────────────────
        storage_status = await self._check_storage_backends()
        checks["storage"] = storage_status
        if storage_status["status"] != "ok":
            overall_status = "degraded"

        # ── Pipeline ────────────────────────────────────────────────
        pipeline_status = await self._check_pipeline()
        checks["pipeline"] = pipeline_status

        # ── LLM Models ─────────────────────────────────────────────
        model_status = self._check_models()
        checks["models"] = model_status
        if model_status["llm_count"] == 0:
            overall_status = "degraded"

        # ── System ──────────────────────────────────────────────────
        checks["system"] = {
            "status": "ok",
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "python_version": self._python_version(),
        }

        result: dict[str, Any] = {
            "status": overall_status,
            "timestamp": time.time(),
            "checks": checks,
        }

        if detailed:
            result["metrics_snapshot"] = metrics.snapshot()

        return result

    async def get_readiness(self) -> dict[str, Any]:
        """Kubernetes-style readiness probe.

        Returns 200 if the server can accept traffic, 503 otherwise.
        """
        ready = True
        reasons: list[str] = []

        # Check if at least one LLM is available
        registry = getattr(self._app.state, "model_registry", None)
        if registry is None:
            ready = False
            reasons.append("model_registry not initialised")
        else:
            llm_count = len(getattr(registry, "_llms", {}))
            if llm_count == 0:
                ready = False
                reasons.append("no LLM models registered")

        # Check if knowledge service is available
        kb_service = getattr(self._app.state, "knowledge_v2_service", None)
        if kb_service is None:
            reasons.append("knowledge_v2_service not initialised")

        return {
            "ready": ready,
            "reasons": reasons,
        }

    async def get_liveness(self) -> dict[str, Any]:
        """Kubernetes-style liveness probe.

        Always returns alive unless the process is in a fatal state.
        """
        return {"alive": True}

    # ── Subsystem Checks ────────────────────────────────────────────

    async def _check_storage_backends(self) -> dict[str, Any]:
        """Probe each storage backend for basic connectivity."""
        backends: dict[str, dict[str, Any]] = {}
        overall = "ok"

        kb_service = getattr(self._app.state, "knowledge_v2_service", None)
        if kb_service is None:
            return {
                "status": "unknown",
                "backends": {},
                "message": "knowledge_v2_service not available",
            }

        # Probe each storage component
        for component_name, attr in [
            ("kv", "_kv"),
            ("vector", "_vector"),
            ("graph", "_graph"),
            ("doc_status", "_doc_status"),
        ]:
            storage = getattr(kb_service, attr, None)
            if storage is None:
                backends[component_name] = {
                    "status": "missing",
                    "type": "unknown",
                }
                overall = "degraded"
                continue

            backend_type = type(storage).__name__
            try:
                # Lightweight probe — check namespace attribute exists
                _ = storage.namespace
                backends[component_name] = {
                    "status": "ok",
                    "type": backend_type,
                }
            except Exception as exc:
                backends[component_name] = {
                    "status": "error",
                    "type": backend_type,
                    "error": str(exc)[:200],
                }
                overall = "degraded"

        return {"status": overall, "backends": backends}

    async def _check_pipeline(self) -> dict[str, Any]:
        """Report pipeline queue state."""
        kb_service = getattr(self._app.state, "knowledge_v2_service", None)
        if kb_service is None:
            return {"status": "unknown", "message": "service not available"}

        pipeline = getattr(kb_service, "_pipeline", None)
        if pipeline is None:
            return {"status": "unknown", "message": "pipeline not initialised"}

        status = pipeline.status
        return {
            "status": "busy" if status.busy else "idle",
            "busy": status.busy,
            "cancelled": status.cancelled,
            "request_pending": status.request_pending,
            "job_name": status.job_name,
            "docs": {
                "total": status.total_docs,
                "processed": status.processed_docs,
                "failed": status.failed_docs,
                "pending": status.pending_docs,
            },
            "stages": {
                "parsing": status.parsing_count,
                "processing": status.processing_count,
            },
            "batches": {
                "total": status.total_batches,
                "current": status.current_batch,
            },
            "latest_message": status.latest_message,
        }

    def _check_models(self) -> dict[str, Any]:
        """Report model registry status."""
        registry = getattr(self._app.state, "model_registry", None)
        if registry is None:
            return {
                "status": "unknown",
                "llm_count": 0,
                "embedding_count": 0,
                "models": [],
            }

        llms = getattr(registry, "_llms", {})
        embeddings = getattr(registry, "_embeddings", {})

        model_list = []
        for name, llm in llms.items():
            model_list.append(
                {
                    "name": name,
                    "type": type(llm).__name__,
                    "kind": "llm",
                }
            )
        for name, emb in embeddings.items():
            model_list.append(
                {
                    "name": name,
                    "type": type(emb).__name__,
                    "kind": "embedding",
                }
            )

        return {
            "status": "ok" if llms else "degraded",
            "llm_count": len(llms),
            "embedding_count": len(embeddings),
            "models": model_list,
        }

    @staticmethod
    def _python_version() -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
