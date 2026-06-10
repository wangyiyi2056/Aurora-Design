"""Bridge between Aurora's in-process metrics/tracing and Langfuse.

The :class:`ObservabilityBridge` listens to events from the existing
:class:`MetricsCollector` and :class:`TraceStore` and forwards relevant
data to Langfuse.  This lets teams that already use the built-in
observability dashboard benefit from Langfuse's richer UI without
modifying any existing code.

The bridge operates in one of two modes:

1. **Push mode** (default) — call :meth:`forward_trace` or
   :meth:`forward_metric_event` to explicitly push data.
2. **Sync mode** — call :meth:`sync_all_traces` to bulk-upload all
   traces from the :class:`TraceStore`.

Usage::

    bridge = ObservabilityBridge()
    bridge.initialise()

    # After a pipeline trace completes:
    bridge.forward_trace(trace_store.get_trace_detail(track_id))

    # After an LLM metric event:
    bridge.forward_metric_event("llm_call", model="gpt-4o", duration_seconds=1.2)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aurora_ext.observability.langfuse_client import (
    LangfuseClient,
    TraceHandle,
    get_langfuse_client,
)

logger = logging.getLogger(__name__)


class ObservabilityBridge:
    """Forward in-process observability data to Langfuse.

    Parameters
    ----------
    client:
        Override the singleton :class:`LangfuseClient`.  When ``None``
        the process-wide instance is used.
    """

    def __init__(self, client: LangfuseClient | None = None) -> None:
        self._client = client or get_langfuse_client()

    # ── Lifecycle ───────────────────────────────────────────────────

    def initialise(self) -> bool:
        """Initialise the underlying Langfuse client.

        Returns ``True`` when tracing is active.
        """
        return self._client.initialise()

    @property
    def is_enabled(self) -> bool:
        return self._client.is_enabled

    def flush(self) -> None:
        self._client.flush()

    def shutdown(self) -> None:
        self._client.shutdown()

    # ── Pipeline trace forwarding ──────────────────────────────────

    def forward_trace(self, trace_detail: dict[str, Any] | None) -> None:
        """Push a :class:`TraceStore` trace detail to Langfuse.

        Parameters
        ----------
        trace_detail:
            Dictionary as returned by
            ``TraceStore.get_trace_detail(track_id)``.  When ``None``
            the call is a no-op.
        """
        if trace_detail is None or not self.is_enabled:
            return

        track_id = trace_detail.get("track_id", "")
        kb_name = trace_detail.get("kb_name", "")
        status = trace_detail.get("status", "")
        spans = trace_detail.get("spans", [])

        tags = ["pipeline"]
        if kb_name:
            tags.append(f"kb:{kb_name}")

        trace = self._client.start_trace(
            name=f"pipeline-{track_id}",
            tags=tags,
            metadata={
                "track_id": track_id,
                "kb_name": kb_name,
                "status": status,
                "total_docs": trace_detail.get("total_docs", 0),
                "processed_docs": trace_detail.get("processed_docs", 0),
                "failed_docs": trace_detail.get("failed_docs", 0),
                "duration_ms": trace_detail.get("duration_ms", 0),
            },
        )

        # Forward each span as a nested observation
        for span_data in spans:
            stage = span_data.get("stage", "")
            span_status = span_data.get("status", "")

            self._client.start_span(
                trace,
                name=f"pipeline::{stage}",
                metadata={
                    "stage": stage,
                    "doc_id": span_data.get("doc_id", ""),
                    "status": span_status,
                    "duration_ms": span_data.get("duration_ms", 0),
                    "error_message": span_data.get("error_message", ""),
                    **{
                        k: v
                        for k, v in span_data.get("metadata", {}).items()
                    },
                },
            )

        # Score the trace based on outcome
        if status == "completed":
            self._client.score(trace, name="pipeline_status", value="completed")
        elif status == "failed":
            self._client.score(trace, name="pipeline_status", value="failed")

        self._client.end_trace(trace, output={"status": status})

    # ── Metric event forwarding ────────────────────────────────────

    def forward_metric_event(
        self,
        event_type: str,
        *,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_seconds: float = 0.0,
        token_count: int = 0,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Forward a metric event to Langfuse as an event observation.

        Parameters
        ----------
        event_type:
            One of ``"llm_call"``, ``"embedding_call"``, ``"cache_result"``.
        model:
            Model name (for LLM / embedding events).
        input_tokens:
            Prompt tokens consumed.
        output_tokens:
            Completion tokens produced.
        duration_seconds:
            Wall-clock duration of the call.
        token_count:
            Token count (for embedding events).
        success:
            Whether the call succeeded.
        metadata:
            Additional metadata.
        """
        if not self.is_enabled:
            return

        tags = [f"metric:{event_type}"]
        if model:
            tags.append(f"model:{model}")

        trace = self._client.start_trace(
            name=f"metric-{event_type}",
            tags=tags,
            metadata=metadata,
        )

        event_meta: dict[str, Any] = {
            "event_type": event_type,
            "duration_ms": round(duration_seconds * 1000, 2),
            "success": success,
        }
        if model:
            event_meta["model"] = model

        if event_type == "llm_call":
            gen = self._client.start_generation(
                trace,
                name=f"metric::llm::{model or 'unknown'}",
                model=model,
                metadata=event_meta,
            )
            self._client.end_generation(
                gen,
                model=model,
                usage={
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                metadata=event_meta,
            )
        else:
            span = self._client.start_span(
                trace,
                name=f"metric::{event_type}",
                metadata=event_meta,
            )
            self._client.end_span(span, metadata=event_meta)

        self._client.end_trace(trace)

    # ── Bulk sync ──────────────────────────────────────────────────

    def sync_all_traces(
        self,
        trace_store: Any,
        *,
        status_filter: str | None = None,
    ) -> int:
        """Bulk-upload all traces from a :class:`TraceStore` to Langfuse.

        Parameters
        ----------
        trace_store:
            A :class:`TraceStore` instance.
        status_filter:
            Optional status filter (``"completed"``, ``"failed"``, etc.).

        Returns
        -------
        int
            Number of traces forwarded.
        """
        if not self.is_enabled:
            return 0

        count = 0
        page = 1
        page_size = 50

        while True:
            traces, total = trace_store.list_traces(
                page=page,
                page_size=page_size,
                status=status_filter,
            )
            if not traces:
                break

            for summary in traces:
                track_id = summary.get("track_id", "")
                detail = trace_store.get_trace_detail(track_id)
                if detail:
                    self.forward_trace(detail)
                    count += 1

            if page * page_size >= total:
                break
            page += 1

        logger.info("Synced %d traces to Langfuse", count)
        return count
