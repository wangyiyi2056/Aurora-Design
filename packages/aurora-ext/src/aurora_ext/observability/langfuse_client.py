"""Langfuse client wrapper — lazy initialisation, safe no-op fallback.

The :class:`LangfuseClient` defers importing and instantiating the Langfuse
SDK until :meth:`get_client` is first called.  When tracing is disabled (or
the SDK is not installed) every method becomes a transparent no-op so that
calling code never needs conditional branches.

Thread-safe singleton access is provided via :func:`get_langfuse_client`.
"""

from __future__ import annotations

import functools
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, AsyncIterator, Callable, Iterator, Optional

from aurora_ext.observability.config import LangfuseConfig

logger = logging.getLogger(__name__)


# ── Lightweight data containers ──────────────────────────────────────


@dataclass(frozen=True)
class TraceHandle:
    """Opaque handle returned by :meth:`LangfuseClient.start_trace`.

    Carries the identifiers needed to attach spans and observations to
    the trace without leaking the underlying Langfuse SDK objects.
    """

    trace_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpanHandle:
    """Opaque handle for a nested observation within a trace."""

    span_id: str
    trace_id: str
    name: str
    parent_id: str = ""


# ── No-op stubs ──────────────────────────────────────────────────────


class _NoOpTrace:
    """Mimics the subset of the Langfuse ``StatefulTraceClient`` API
    used by this module so that disabled-mode code paths stay identical."""

    def __init__(self, trace_id: str) -> None:
        self.id = trace_id

    def span(self, **_: Any) -> _NoOpTrace:
        return self

    def generation(self, **_: Any) -> _NoOpTrace:
        return self

    def event(self, **_: Any) -> _NoOpTrace:
        return self

    def update(self, **_: Any) -> None:
        pass

    def end(self, **_: Any) -> None:
        pass

    def score(self, **_: Any) -> None:
        pass


# ── Client ───────────────────────────────────────────────────────────


class LangfuseClient:
    """High-level wrapper around the Langfuse Python SDK.

    Parameters
    ----------
    config:
        A :class:`LangfuseConfig` instance.  When ``config.is_configured``
        is ``False`` the client operates in no-op mode.

    Usage::

        client = LangfuseClient(config)
        client.initialise()

        trace = client.start_trace(name="rag-query")
        gen = client.start_generation(
            trace,
            name="llm-call",
            model="gpt-4o",
            input=[{"role": "user", "content": "Hello"}],
        )
        client.end_generation(gen, output="Hi!", usage={"prompt_tokens": 5, "completion_tokens": 3})
        client.end_trace(trace)

        client.flush()
    """

    def __init__(self, config: LangfuseConfig) -> None:
        self._config = config
        self._langfuse: Any = None  # lazily imported
        self._lock = Lock()
        self._initialised = False
        self._init_failed = False

    # ── Properties ──────────────────────────────────────────────────

    @property
    def is_enabled(self) -> bool:
        """Return ``True`` when tracing is active (configured + SDK loaded)."""
        return self._initialised and self._langfuse is not None

    @property
    def config(self) -> LangfuseConfig:
        return self._config

    # ── Lifecycle ───────────────────────────────────────────────────

    def initialise(self) -> bool:
        """Import the SDK and create the Langfuse client.

        Returns ``True`` on success, ``False`` if disabled or the SDK
        is missing.  Safe to call multiple times — subsequent calls
        are no-ops.
        """
        if self._initialised or self._init_failed:
            return self._initialised

        with self._lock:
            if self._initialised or self._init_failed:
                return self._initialised

            if not self._config.is_configured:
                logger.debug(
                    "Langfuse tracing disabled (enabled=%s, keys=%s)",
                    self._config.enabled,
                    "present" if self._config.public_key else "missing",
                )
                self._init_failed = True
                return False

            try:
                from langfuse import Langfuse  # type: ignore[import-untyped]

                self._langfuse = Langfuse(
                    public_key=self._config.public_key,
                    secret_key=self._config.secret_key,
                    host=self._config.host,
                    debug=self._config.debug,
                    flush_interval=self._config.flush_interval,
                    sample_rate=self._config.sample_rate,
                    release=self._config.release or None,
                )
                self._initialised = True
                logger.info(
                    "Langfuse tracing initialised (host=%s, project=%s)",
                    self._config.host,
                    self._config.project_name,
                )
                return True

            except ImportError:
                logger.warning(
                    "langfuse package not installed — tracing disabled. "
                    "Install with: pip install langfuse"
                )
                self._init_failed = True
                return False
            except Exception as exc:
                logger.error("Failed to initialise Langfuse: %s", exc)
                self._init_failed = True
                return False

    def flush(self) -> None:
        """Force-flush queued observations to the Langfuse server."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)

    def shutdown(self) -> None:
        """Flush and release resources."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.flush()
            self._langfuse.shutdown()
        except Exception as exc:
            logger.warning("Langfuse shutdown failed: %s", exc)
        self._initialised = False
        self._langfuse = None

    # ── Trace operations ────────────────────────────────────────────

    def start_trace(
        self,
        *,
        name: str = "aurora-trace",
        user_id: str = "",
        session_id: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceHandle:
        """Create a new top-level trace.

        Returns a :class:`TraceHandle` used to attach observations.
        In no-op mode the handle still carries a synthetic ``trace_id``
        so that calling code doesn't need conditional logic.
        """
        trace_id = uuid.uuid4().hex[:16]

        if not self.is_enabled:
            return TraceHandle(trace_id=trace_id, name=name, metadata=metadata or {})

        all_tags = list(self._config.default_tags) + (tags or [])
        merged_meta: dict[str, Any] = {}
        if self._config.project_name:
            merged_meta["project"] = self._config.project_name
        if metadata:
            merged_meta.update(metadata)

        try:
            self._langfuse.trace(
                id=trace_id,
                name=name,
                user_id=user_id or None,
                session_id=session_id or None,
                tags=all_tags or None,
                metadata=merged_meta or None,
            )
        except Exception as exc:
            logger.warning("Langfuse start_trace failed: %s", exc)

        return TraceHandle(trace_id=trace_id, name=name, metadata=metadata or {})

    def end_trace(self, handle: TraceHandle, *, output: Any = None) -> None:
        """Mark a trace as complete."""
        if not self.is_enabled:
            return
        try:
            trace_obj = self._langfuse.get_trace(handle.trace_id)
            if trace_obj and hasattr(trace_obj, "update"):
                trace_obj.update(output=output)
        except Exception as exc:
            logger.warning("Langfuse end_trace failed: %s", exc)

    def start_span(
        self,
        trace: TraceHandle,
        *,
        name: str = "span",
        parent_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SpanHandle:
        """Create a nested span within a trace."""
        span_id = uuid.uuid4().hex[:16]

        if not self.is_enabled:
            return SpanHandle(
                span_id=span_id, trace_id=trace.trace_id, name=name, parent_id=parent_id
            )

        try:
            self._langfuse.span(
                id=span_id,
                trace_id=trace.trace_id,
                name=name,
                parent_observation_id=parent_id or None,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Langfuse start_span failed: %s", exc)

        return SpanHandle(
            span_id=span_id, trace_id=trace.trace_id, name=name, parent_id=parent_id
        )

    def end_span(
        self,
        handle: SpanHandle,
        *,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark a span as complete."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.span(
                id=handle.span_id,
                trace_id=handle.trace_id,
                output=output,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Langfuse end_span failed: %s", exc)

    def start_generation(
        self,
        trace: TraceHandle,
        *,
        name: str = "generation",
        model: str = "",
        input: Any = None,
        parent_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SpanHandle:
        """Create an LLM generation observation.

        Generations differ from spans in that they carry ``model``,
        ``input``, ``output``, and ``usage`` fields that Langfuse
        renders specially in the UI.
        """
        span_id = uuid.uuid4().hex[:16]

        if not self.is_enabled:
            return SpanHandle(
                span_id=span_id, trace_id=trace.trace_id, name=name, parent_id=parent_id
            )

        try:
            self._langfuse.generation(
                id=span_id,
                trace_id=trace.trace_id,
                name=name,
                model=model or None,
                input=input,
                parent_observation_id=parent_id or None,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Langfuse start_generation failed: %s", exc)

        return SpanHandle(
            span_id=span_id, trace_id=trace.trace_id, name=name, parent_id=parent_id
        )

    def end_generation(
        self,
        handle: SpanHandle,
        *,
        output: Any = None,
        model: str = "",
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Complete a generation with output and token usage."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.generation(
                id=handle.span_id,
                trace_id=handle.trace_id,
                output=output,
                model=model or None,
                usage=usage,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Langfuse end_generation failed: %s", exc)

    def record_event(
        self,
        trace: TraceHandle,
        *,
        name: str = "event",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a discrete event within a trace."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.event(
                trace_id=trace.trace_id,
                name=name,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Langfuse record_event failed: %s", exc)

    def score(
        self,
        trace: TraceHandle,
        *,
        name: str,
        value: float | str,
        comment: str = "",
    ) -> None:
        """Attach a score to a trace (e.g. relevance, correctness)."""
        if not self.is_enabled:
            return
        try:
            self._langfuse.score(
                trace_id=trace.trace_id,
                name=name,
                value=value,
                comment=comment or None,
            )
        except Exception as exc:
            logger.warning("Langfuse score failed: %s", exc)


# ── Singleton Access ─────────────────────────────────────────────────

_instance: LangfuseClient | None = None
_instance_lock = Lock()


def get_langfuse_client(config: LangfuseConfig | None = None) -> LangfuseClient:
    """Return the process-wide :class:`LangfuseClient` singleton.

    On first call the client is created (but **not** initialised — call
    :meth:`LangfuseClient.initialise` to trigger SDK loading).
    """
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                if config is None:
                    from aurora_ext.observability.config import load_langfuse_config
                    config = load_langfuse_config()
                _instance = LangfuseClient(config)
    return _instance


def reset_langfuse_client() -> None:
    """Tear down the singleton (for testing)."""
    global _instance
    if _instance is not None:
        with _instance_lock:
            if _instance is not None:
                _instance.shutdown()
                _instance = None
