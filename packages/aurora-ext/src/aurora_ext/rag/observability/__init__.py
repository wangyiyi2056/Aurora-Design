"""Observability primitives for the RAG pipeline.

Provides in-memory metrics collection, pipeline tracing, and
Prometheus-compatible export without external dependencies.
"""

from aurora_ext.rag.observability.metrics import MetricsCollector, get_metrics
from aurora_ext.rag.observability.tracing import (
    PipelineTrace,
    PipelineSpan,
    SpanStatus,
    TraceStore,
    get_trace_store,
)

__all__ = [
    "MetricsCollector",
    "get_metrics",
    "PipelineTrace",
    "PipelineSpan",
    "SpanStatus",
    "TraceStore",
    "get_trace_store",
]
