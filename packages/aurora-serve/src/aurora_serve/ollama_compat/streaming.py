"""NDJSON streaming helpers for the Ollama compat layer.

Each helper yields newline-delimited JSON strings suitable for
``StreamingResponse`` with ``media_type="application/x-ndjson"``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from aurora_serve.ollama_compat.mapper import count_tokens


def now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def ndjson(obj: dict[str, Any]) -> str:
    """Serialise a dict as a single NDJSON line."""
    return json.dumps(obj) + "\n"


async def stream_chat_response(
    result: dict[str, Any],
    model_name: str,
    prompt_text: str,
) -> AsyncGenerator[str, None]:
    """Yield NDJSON chat chunks from a RAG query result.

    Handles both streaming (async iterator) and non-streaming (complete
    response text) modes.
    """
    start = time.monotonic()
    prompt_tokens = count_tokens(prompt_text)
    full_response = ""

    try:
        stream_iter = result.get("stream_iterator")
        if stream_iter is not None:
            async for chunk in stream_iter:
                full_response += chunk
                yield ndjson({
                    "model": model_name,
                    "created_at": now_iso(),
                    "message": {"role": "assistant", "content": chunk},
                    "done": False,
                })
        else:
            full_response = result.get("response", "")
            yield ndjson({
                "model": model_name,
                "created_at": now_iso(),
                "message": {"role": "assistant", "content": full_response},
                "done": False,
            })

        elapsed_ns = int((time.monotonic() - start) * 1_000_000_000)
        yield ndjson({
            "model": model_name,
            "created_at": now_iso(),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "total_duration": elapsed_ns,
            "prompt_eval_count": prompt_tokens,
            "eval_count": count_tokens(full_response),
        })
    except Exception as exc:
        yield ndjson({
            "model": model_name,
            "created_at": now_iso(),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "error": str(exc),
        })


async def stream_generate_response(
    result: dict[str, Any],
    model_name: str,
    prompt_text: str,
) -> AsyncGenerator[str, None]:
    """Yield NDJSON generate chunks from a raw LLM result.

    Handles both streaming (async iterator) and non-streaming (complete
    response text) modes.
    """
    start = time.monotonic()
    prompt_tokens = count_tokens(prompt_text)
    full_response = ""

    try:
        stream_iter = result.get("stream_iterator")
        if stream_iter is not None:
            async for chunk in stream_iter:
                full_response += chunk
                yield ndjson({
                    "model": model_name,
                    "created_at": now_iso(),
                    "response": chunk,
                    "done": False,
                })
        else:
            full_response = result.get("response", "")
            yield ndjson({
                "model": model_name,
                "created_at": now_iso(),
                "response": full_response,
                "done": False,
            })

        elapsed_ns = int((time.monotonic() - start) * 1_000_000_000)
        yield ndjson({
            "model": model_name,
            "created_at": now_iso(),
            "response": "",
            "done": True,
            "total_duration": elapsed_ns,
            "prompt_eval_count": prompt_tokens,
            "eval_count": count_tokens(full_response),
        })
    except Exception as exc:
        yield ndjson({"error": str(exc)}) + "\n"
