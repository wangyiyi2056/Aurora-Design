"""Pipeline tracing — record and query per-document processing spans.

Each pipeline ingestion creates a :class:`PipelineTrace` identified by
``track_id``.  Within the trace, individual processing stages (parse,
chunk, extract, embed) are recorded as :class:`PipelineSpan` entries.

Traces are stored in-memory with configurable retention.  The
:class:`TraceStore` is a process-wide singleton accessible via
:func:`get_trace_store`.
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Optional


class SpanStatus(str, Enum):
    """Outcome status for a trace span."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineSpan:
    """A single processing stage within a pipeline trace."""

    span_id: str = ""
    track_id: str = ""
    doc_id: str = ""
    stage: str = ""  # "parse", "chunk", "extract", "embed", "merge"
    status: SpanStatus = SpanStatus.PENDING
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: float = 0.0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark this span as running."""
        self.status = SpanStatus.RUNNING
        self.started_at = time.time()

    def finish(self, *, error: str = "") -> None:
        """Mark this span as completed or failed."""
        self.finished_at = time.time()
        if self.started_at > 0:
            self.duration_ms = (self.finished_at - self.started_at) * 1000
        if error:
            self.status = SpanStatus.FAILED
            self.error_message = error
        else:
            self.status = SpanStatus.COMPLETED

    def skip(self, reason: str = "") -> None:
        """Mark this span as skipped."""
        self.status = SpanStatus.SKIPPED
        self.finished_at = time.time()
        if reason:
            self.metadata["skip_reason"] = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "track_id": self.track_id,
            "doc_id": self.doc_id,
            "stage": self.stage,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class PipelineTrace:
    """A collection of spans for a single pipeline batch (track_id)."""

    track_id: str
    kb_name: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    total_docs: int = 0
    processed_docs: int = 0
    failed_docs: int = 0
    status: str = "running"  # "running", "completed", "failed", "cancelled"
    spans: list[PipelineSpan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        end = self.finished_at if self.finished_at > 0 else time.time()
        return (end - self.created_at) * 1000

    def add_span(
        self,
        *,
        doc_id: str,
        stage: str,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineSpan:
        """Create and return a new span for this trace."""
        span = PipelineSpan(
            span_id=uuid.uuid4().hex[:12],
            track_id=self.track_id,
            doc_id=doc_id,
            stage=stage,
            metadata=metadata or {},
        )
        span.start()
        self.spans.append(span)
        return span

    def finish(self, *, status: str = "completed") -> None:
        """Mark the trace as finished."""
        self.finished_at = time.time()
        self.status = status

    def to_dict(self, *, include_spans: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "track_id": self.track_id,
            "kb_name": self.kb_name,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "total_docs": self.total_docs,
            "processed_docs": self.processed_docs,
            "failed_docs": self.failed_docs,
            "status": self.status,
            "metadata": self.metadata,
            "span_count": len(self.spans),
        }
        if include_spans:
            # Aggregate stage summaries
            stage_summary: dict[str, dict[str, Any]] = {}
            for span in self.spans:
                st = stage_summary.setdefault(
                    span.stage,
                    {"count": 0, "total_ms": 0.0, "failed": 0, "completed": 0},
                )
                st["count"] += 1
                st["total_ms"] += span.duration_ms
                if span.status == SpanStatus.COMPLETED:
                    st["completed"] += 1
                elif span.status == SpanStatus.FAILED:
                    st["failed"] += 1
            result["stage_summary"] = {
                k: {**v, "avg_ms": round(v["total_ms"] / max(v["count"], 1), 2)}
                for k, v in stage_summary.items()
            }
            result["spans"] = [s.to_dict() for s in self.spans]
        return result


class TraceStore:
    """In-memory trace storage with bounded retention.

    Thread-safe.  Access the process-wide instance via
    :func:`get_trace_store`.

    Parameters
    ----------
    max_traces:
        Maximum number of traces to retain.  Oldest traces are evicted
        when the limit is reached.
    """

    def __init__(self, max_traces: int = 500) -> None:
        self._lock = Lock()
        self._max_traces = max_traces
        self._traces: OrderedDict[str, PipelineTrace] = OrderedDict()

    def create_trace(
        self,
        track_id: str,
        *,
        kb_name: str = "",
        total_docs: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineTrace:
        """Create and register a new trace."""
        trace = PipelineTrace(
            track_id=track_id,
            kb_name=kb_name,
            total_docs=total_docs,
            metadata=metadata or {},
        )
        with self._lock:
            self._traces[track_id] = trace
            self._evict_if_needed()
        return trace

    def get_trace(self, track_id: str) -> PipelineTrace | None:
        """Look up a trace by its track_id."""
        with self._lock:
            return self._traces.get(track_id)

    def list_traces(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        kb_name: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List traces with pagination and optional filtering.

        Returns ``(traces, total_count)`` where traces are ordered
        newest-first.
        """
        with self._lock:
            all_traces = list(self._traces.values())

        # Apply filters
        if status:
            all_traces = [t for t in all_traces if t.status == status]
        if kb_name:
            all_traces = [t for t in all_traces if t.kb_name == kb_name]

        # Sort newest first
        all_traces.sort(key=lambda t: t.created_at, reverse=True)
        total = len(all_traces)

        # Paginate
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        page_traces = all_traces[start:end]

        return [t.to_dict(include_spans=False) for t in page_traces], total

    def get_trace_detail(self, track_id: str) -> dict[str, Any] | None:
        """Return the full trace detail including all spans."""
        trace = self.get_trace(track_id)
        if trace is None:
            return None
        return trace.to_dict(include_spans=True)

    def _evict_if_needed(self) -> None:
        """Remove oldest traces if over capacity.  Must hold ``_lock``."""
        while len(self._traces) > self._max_traces:
            self._traces.popitem(last=False)

    def stats(self) -> dict[str, Any]:
        """Return summary statistics for all stored traces."""
        with self._lock:
            traces = list(self._traces.values())

        total = len(traces)
        running = sum(1 for t in traces if t.status == "running")
        completed = sum(1 for t in traces if t.status == "completed")
        failed = sum(1 for t in traces if t.status == "failed")
        cancelled = sum(1 for t in traces if t.status == "cancelled")
        total_docs = sum(t.total_docs for t in traces)
        total_processed = sum(t.processed_docs for t in traces)
        total_failed = sum(t.failed_docs for t in traces)

        return {
            "total_traces": total,
            "max_traces": self._max_traces,
            "by_status": {
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
            },
            "total_docs": total_docs,
            "total_processed": total_processed,
            "total_failed": total_failed,
        }

    def reset(self) -> None:
        """Clear all traces (useful for testing)."""
        with self._lock:
            self._traces.clear()


# ── Singleton Access ─────────────────────────────────────────────────

_instance: TraceStore | None = None
_instance_lock = Lock()


def get_trace_store() -> TraceStore:
    """Return the process-wide :class:`TraceStore` singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TraceStore()
    return _instance
