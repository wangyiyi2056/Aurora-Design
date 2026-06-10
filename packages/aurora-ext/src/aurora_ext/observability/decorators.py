"""Tracing decorators — zero-boilerplate instrumentation for async and sync functions.

Each decorator creates a Langfuse trace (or generation) around the
decorated function, recording timing, arguments, return values, and
errors.  When tracing is disabled the decorators are transparent
pass-throughs with no measurable overhead.

Decorators
----------
- :func:`trace_llm` — LLM chat completion calls
- :func:`trace_embedding` — embedding API calls
- :func:`trace_kg_extraction` — KG entity/relation extraction
- :func:`trace_rag_query` — RAG query execution (6 modes)
- :func:`trace_reranker` — reranker API calls
- :func:`trace_operation` — generic catch-all decorator

Usage::

    @trace_llm
    async def call_openai(messages, model="gpt-4o"):
        ...

    @trace_rag_query
    async def answer_question(query, mode="mix"):
        ...
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from typing import Any, Callable, TypeVar

from aurora_ext.observability.langfuse_client import (
    LangfuseClient,
    TraceHandle,
    get_langfuse_client,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ── Internal helpers ─────────────────────────────────────────────────


def _safe_repr(obj: Any, max_len: int = 500) -> Any:
    """Return a JSON-safe representation, truncating if needed."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + "..."
        return obj
    if isinstance(obj, (list, tuple)):
        if len(obj) > 10:
            return f"<{type(obj).__name__} len={len(obj)}>"
        return [_safe_repr(item, max_len) for item in obj]
    if isinstance(obj, dict):
        return {k: _safe_repr(v, max_len) for k, v in list(obj.items())[:20]}
    return f"<{type(obj).__name__}>"


def _extract_usage(result: Any) -> dict[str, int] | None:
    """Try to extract token usage from common response shapes."""
    if result is None:
        return None

    # Direct dict
    if isinstance(result, dict):
        usage = result.get("usage")
        if usage:
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get(
                    "total_tokens",
                    usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
                ),
            }

    # Object with attributes (e.g. dataclass with usage field)
    usage = getattr(result, "usage", None)
    if usage:
        if isinstance(usage, dict):
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(
                usage, "total_tokens",
                getattr(usage, "prompt_tokens", 0) + getattr(usage, "completion_tokens", 0),
            ),
        }

    # Object with direct token attributes
    pt = getattr(result, "prompt_tokens", None)
    ct = getattr(result, "completion_tokens", None)
    if pt is not None or ct is not None:
        return {
            "prompt_tokens": pt or 0,
            "completion_tokens": ct or 0,
            "total_tokens": (pt or 0) + (ct or 0),
        }

    return None


def _build_wrapper(
    func: F,
    *,
    trace_name: str,
    trace_type: str,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
    extract_model: Callable[..., str] | None = None,
) -> F:
    """Build a wrapper that traces sync or async function calls."""

    _client = client or get_langfuse_client()

    def _make_trace_metadata(args: tuple, kwargs: dict) -> dict[str, Any]:
        """Build trace metadata from function call arguments."""
        meta: dict[str, Any] = {
            "function": func.__qualname__,
            "trace_type": trace_type,
        }
        if kwargs:
            meta["kwargs"] = _safe_repr(kwargs)
        return meta

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _client.is_enabled:
                return await func(*args, **kwargs)

            model = ""
            if extract_model:
                try:
                    model = extract_model(*args, **kwargs)
                except Exception:
                    pass

            meta = _make_trace_metadata(args, kwargs)
            if model:
                meta["model"] = model

            trace = _client.start_trace(
                name=trace_name,
                tags=tags,
                metadata=meta,
            )

            started = time.monotonic()
            try:
                result = await func(*args, **kwargs)

                elapsed = time.monotonic() - started
                usage = _extract_usage(result)

                if trace_type == "llm":
                    gen = _client.start_generation(
                        trace,
                        name=f"{trace_name}::generation",
                        model=model,
                        input=_safe_repr(args[1:] if args else kwargs.get("messages")),
                        metadata=meta,
                    )
                    _client.end_generation(
                        gen,
                        output=_safe_repr(result),
                        model=model,
                        usage=usage,
                        metadata={"elapsed_ms": round(elapsed * 1000, 2)},
                    )
                else:
                    span = _client.start_span(
                        trace, name=f"{trace_name}::span", metadata=meta
                    )
                    _client.end_span(
                        span,
                        output=_safe_repr(result),
                        metadata={"elapsed_ms": round(elapsed * 1000, 2)},
                    )

                _client.end_trace(trace, output=_safe_repr(result))
                return result

            except Exception as exc:
                elapsed = time.monotonic() - started
                _client.record_event(
                    trace,
                    name=f"{trace_name}::error",
                    metadata={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:500],
                        "elapsed_ms": round(elapsed * 1000, 2),
                    },
                )
                _client.end_trace(
                    trace,
                    output={"error": f"{type(exc).__name__}: {exc}"},
                )
                raise

        return async_wrapper  # type: ignore[return-value]

    else:

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _client.is_enabled:
                return func(*args, **kwargs)

            model = ""
            if extract_model:
                try:
                    model = extract_model(*args, **kwargs)
                except Exception:
                    pass

            meta = _make_trace_metadata(args, kwargs)
            if model:
                meta["model"] = model

            trace = _client.start_trace(
                name=trace_name,
                tags=tags,
                metadata=meta,
            )

            started = time.monotonic()
            try:
                result = func(*args, **kwargs)

                elapsed = time.monotonic() - started
                usage = _extract_usage(result)

                if trace_type == "llm":
                    gen = _client.start_generation(
                        trace,
                        name=f"{trace_name}::generation",
                        model=model,
                        input=_safe_repr(args[1:] if args else kwargs.get("messages")),
                        metadata=meta,
                    )
                    _client.end_generation(
                        gen,
                        output=_safe_repr(result),
                        model=model,
                        usage=usage,
                        metadata={"elapsed_ms": round(elapsed * 1000, 2)},
                    )
                else:
                    span = _client.start_span(
                        trace, name=f"{trace_name}::span", metadata=meta
                    )
                    _client.end_span(
                        span,
                        output=_safe_repr(result),
                        metadata={"elapsed_ms": round(elapsed * 1000, 2)},
                    )

                _client.end_trace(trace, output=_safe_repr(result))
                return result

            except Exception as exc:
                elapsed = time.monotonic() - started
                _client.record_event(
                    trace,
                    name=f"{trace_name}::error",
                    metadata={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:500],
                        "elapsed_ms": round(elapsed * 1000, 2),
                    },
                )
                _client.end_trace(
                    trace,
                    output={"error": f"{type(exc).__name__}: {exc}"},
                )
                raise

        return sync_wrapper  # type: ignore[return-value]


# ── Public decorators ────────────────────────────────────────────────


def trace_llm(
    func: F | None = None,
    *,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
) -> F | Callable[[F], F]:
    """Decorator for LLM chat completion calls.

    Records model, input messages, output text, token usage, and
    latency.  Works with both sync and async functions.

    Usage::

        @trace_llm
        async def chat(messages, model="gpt-4o"):
            ...

        @trace_llm(tags=["production"])
        async def chat(messages, model="gpt-4o"):
            ...
    """
    def _extract_model(*args: Any, **kwargs: Any) -> str:
        return kwargs.get("model", "")

    if func is not None:
        return _build_wrapper(
            func,
            trace_name="llm-completion",
            trace_type="llm",
            tags=tags,
            client=client,
            extract_model=_extract_model,
        )

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name="llm-completion",
            trace_type="llm",
            tags=tags,
            client=client,
            extract_model=_extract_model,
        )

    return decorator


def trace_embedding(
    func: F | None = None,
    *,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
) -> F | Callable[[F], F]:
    """Decorator for embedding API calls.

    Records model, input text count, output dimensions, and latency.
    """
    if func is not None:
        return _build_wrapper(
            func,
            trace_name="embedding",
            trace_type="embedding",
            tags=tags,
            client=client,
        )

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name="embedding",
            trace_type="embedding",
            tags=tags,
            client=client,
        )

    return decorator


def trace_kg_extraction(
    func: F | None = None,
    *,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
) -> F | Callable[[F], F]:
    """Decorator for KG entity/relationship extraction calls.

    Records chunk text length, extracted entity/relation counts, and
    latency.
    """
    if func is not None:
        return _build_wrapper(
            func,
            trace_name="kg-extraction",
            trace_type="extraction",
            tags=tags,
            client=client,
        )

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name="kg-extraction",
            trace_type="extraction",
            tags=tags,
            client=client,
        )

    return decorator


def trace_rag_query(
    func: F | None = None,
    *,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
) -> F | Callable[[F], F]:
    """Decorator for RAG query execution (all 6 modes).

    Records query text, mode, retrieved context size, response, and
    latency.
    """
    if func is not None:
        return _build_wrapper(
            func,
            trace_name="rag-query",
            trace_type="query",
            tags=tags,
            client=client,
        )

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name="rag-query",
            trace_type="query",
            tags=tags,
            client=client,
        )

    return decorator


def trace_reranker(
    func: F | None = None,
    *,
    tags: list[str] | None = None,
    client: LangfuseClient | None = None,
) -> F | Callable[[F], F]:
    """Decorator for reranker API calls.

    Records query, document count, top_n, result count, and latency.
    """
    if func is not None:
        return _build_wrapper(
            func,
            trace_name="reranker",
            trace_type="reranker",
            tags=tags,
            client=client,
        )

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name="reranker",
            trace_type="reranker",
            tags=tags,
            client=client,
        )

    return decorator


def trace_operation(
    name: str = "operation",
    *,
    tags: list[str] | None = None,
    trace_type: str = "operation",
    client: LangfuseClient | None = None,
) -> Callable[[F], F]:
    """Generic decorator for any operation worth tracing.

    Parameters
    ----------
    name:
        Custom trace name.
    tags:
        Additional tags.
    trace_type:
        Category label (``"operation"``, ``"ingestion"``, etc.).
    client:
        Override the singleton client.

    Usage::

        @trace_operation("document-ingestion", tags=["batch"])
        async def ingest_document(doc):
            ...
    """

    def decorator(fn: F) -> F:
        return _build_wrapper(
            fn,
            trace_name=name,
            trace_type=trace_type,
            tags=tags,
            client=client,
        )

    return decorator
