"""Context managers for structured Langfuse tracing.

Provides :func:`trace_span` and :func:`trace_generation` — lightweight
context managers that create a Langfuse trace (or span), measure
elapsed time, and auto-finalise on exit.  In disabled mode the
context managers are zero-overhead pass-throughs.

Usage::

    with trace_span("kg-extraction", kb_name="default") as ctx:
        # ... do work ...
        ctx.add_metadata("doc_count", 42)

    with trace_generation("llm-call", model="gpt-4o") as ctx:
        # ... call LLM ...
        ctx.set_output("Hello, world!")
        ctx.set_usage(prompt_tokens=10, completion_tokens=5)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

from aurora_ext.observability.langfuse_client import (
    LangfuseClient,
    SpanHandle,
    TraceHandle,
    get_langfuse_client,
)

logger = logging.getLogger(__name__)


# ── Context objects ──────────────────────────────────────────────────


@dataclass
class TraceContext:
    """Mutable context yielded by :func:`trace_span` / :func:`trace_generation`.

    Allows the caller to enrich the trace before it is finalised on
    context-manager exit.
    """

    trace_id: str
    name: str
    _client: LangfuseClient
    _trace_handle: TraceHandle
    _span_handle: SpanHandle | None = None
    _started_at: float = field(default_factory=time.monotonic)
    _metadata: dict[str, Any] = field(default_factory=dict)
    _output: Any = None
    _error: str = ""
    _usage: dict[str, int] = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_at

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_seconds * 1000

    def add_metadata(self, key: str, value: Any) -> None:
        """Attach a metadata key-value pair to the trace."""
        self._metadata[key] = value

    def set_output(self, output: Any) -> None:
        """Set the trace output (string, dict, or list)."""
        self._output = output

    def set_error(self, message: str) -> None:
        """Record an error message without raising."""
        self._error = message

    def set_usage(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        """Record token usage for an LLM generation."""
        self._usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
        }


# ── Context managers ─────────────────────────────────────────────────


@contextmanager
def trace_span(
    name: str,
    *,
    user_id: str = "",
    session_id: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    client: LangfuseClient | None = None,
) -> Generator[TraceContext, None, None]:
    """Create a top-level trace and span, auto-finalising on exit.

    Parameters
    ----------
    name:
        Human-readable trace name (e.g. ``"kg-extraction"``).
    user_id:
        Optional user identifier for attribution.
    session_id:
        Optional session identifier for grouping.
    tags:
        Additional tags merged with the config's ``default_tags``.
    metadata:
        Initial metadata dictionary.
    client:
        Override the singleton client (useful for testing).

    Yields
    ------
    TraceContext
        Mutable context for enriching the trace before finalisation.
    """
    _client = client or get_langfuse_client()

    trace_handle = _client.start_trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        metadata=metadata,
    )

    ctx = TraceContext(
        trace_id=trace_handle.trace_id,
        name=name,
        _client=_client,
        _trace_handle=trace_handle,
    )

    if metadata:
        ctx._metadata.update(metadata)

    try:
        yield ctx
    except Exception as exc:
        ctx.set_error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        # Merge any metadata accumulated during the span
        if ctx._metadata:
            trace_handle = TraceHandle(
                trace_id=trace_handle.trace_id,
                name=trace_handle.name,
                metadata={**trace_handle.metadata, **ctx._metadata},
            )

        # Finalise
        _client.end_trace(trace_handle, output=ctx._output)


@contextmanager
def trace_generation(
    name: str,
    *,
    model: str = "",
    input: Any = None,
    user_id: str = "",
    session_id: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    client: LangfuseClient | None = None,
) -> Generator[TraceContext, None, None]:
    """Create a trace with an LLM generation observation.

    Similar to :func:`trace_span` but creates a *generation* observation
    (with ``model``, ``input``, ``output``, ``usage``) instead of a
    plain span.  This is the preferred context manager for LLM calls.

    Usage::

        with trace_generation("chat-completion", model="gpt-4o") as ctx:
            response = await llm.achat(messages)
            ctx.set_output(response.text)
            ctx.set_usage(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
    """
    _client = client or get_langfuse_client()

    trace_handle = _client.start_trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        metadata=metadata,
    )

    gen_handle = _client.start_generation(
        trace_handle,
        name=name,
        model=model,
        input=input,
        metadata=metadata,
    )

    ctx = TraceContext(
        trace_id=trace_handle.trace_id,
        name=name,
        _client=_client,
        _trace_handle=trace_handle,
        _span_handle=gen_handle,
    )

    if metadata:
        ctx._metadata.update(metadata)

    try:
        yield ctx
    except Exception as exc:
        ctx.set_error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        # End the generation observation
        _client.end_generation(
            gen_handle,
            output=ctx._output,
            model=model,
            usage=ctx._usage or None,
            metadata=ctx._metadata or None,
        )

        # End the trace
        _client.end_trace(trace_handle, output=ctx._output)


@contextmanager
def nested_span(
    parent_ctx: TraceContext,
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Generator[TraceContext, None, None]:
    """Create a child span within an existing trace context.

    Parameters
    ----------
    parent_ctx:
        The parent :class:`TraceContext` from :func:`trace_span` or
        :func:`trace_generation`.
    name:
        Child span name.
    metadata:
        Initial metadata dictionary.

    Yields
    ------
    TraceContext
        A new context scoped to the child span.
    """
    _client = parent_ctx._client

    parent_id = ""
    if parent_ctx._span_handle:
        parent_id = parent_ctx._span_handle.span_id

    child_span = _client.start_span(
        parent_ctx._trace_handle,
        name=name,
        parent_id=parent_id,
        metadata=metadata,
    )

    child_ctx = TraceContext(
        trace_id=parent_ctx.trace_id,
        name=name,
        _client=_client,
        _trace_handle=parent_ctx._trace_handle,
        _span_handle=child_span,
    )

    if metadata:
        child_ctx._metadata.update(metadata)

    try:
        yield child_ctx
    except Exception as exc:
        child_ctx.set_error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _client.end_span(
            child_span,
            output=child_ctx._output,
            metadata=child_ctx._metadata or None,
        )
