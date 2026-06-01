"""Ollama-compatible API routes.

Provides a drop-in shim so that Ollama-aware clients (Open WebUI, etc.)
can talk to the Aurora RAG knowledge base.  The ``/chat`` endpoint routes
queries through the RAG engine based on mode prefixes in the message text.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from aurora_serve.knowledge.v2.schemas import (
    OllamaChatRequest,
    OllamaGenerateRequest,
    OllamaMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ollama"])

# Default knowledge base name for Ollama API — configurable via env var.
_DEFAULT_KB = os.environ.get("OLLAMA_DEFAULT_KB", "default")


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Constants ────────────────────────────────────────────────────────

_MODEL_NAME = os.getenv("OLLAMA_EMULATING_MODEL_NAME", "lightrag")
_MODEL_TAG = os.getenv("OLLAMA_EMULATING_MODEL_TAG", "latest")

_MODE_PREFIXES: dict[str, str] = {
    "/local": "local",
    "/global": "global",
    "/hybrid": "hybrid",
    "/naive": "naive",
    "/mix": "mix",
    "/bypass": "bypass",
    "/context": "mix",
    "/localcontext": "local",
    "/globalcontext": "global",
    "/hybridcontext": "hybrid",
    "/naivecontext": "naive",
    "/mixcontext": "mix",
}

_OPENWEBUI_MARKER = "\n<chat_history>\nUSER:"


# ── Helpers ──────────────────────────────────────────────────────────


def _count_tokens(text: str) -> int:
    """Best-effort token count using tiktoken, falling back to heuristic."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _parse_mode_and_query(content: str) -> tuple[str, str]:
    """Extract RAG mode prefix and clean query from message content.

    Returns ``(mode, clean_query)``.
    """
    stripped = content.strip()
    for prefix, mode in sorted(_MODE_PREFIXES.items(), key=lambda kv: -len(kv[0])):
        if stripped.startswith(prefix):
            clean = stripped[len(prefix):].strip()
            return mode, clean
    return "mix", stripped


def _is_openwebui_passthrough(content: str) -> bool:
    """Detect the OpenWebUI chat_history pattern that should bypass RAG."""
    return _OPENWEBUI_MARKER in content


def _build_conversation_history(messages: list[OllamaMessage]) -> list[dict[str, str]]:
    """Convert OllamaMessage list to conversation_history dicts, excluding the last user msg."""
    history: list[dict[str, str]] = []
    for msg in messages[:-1] if messages else []:
        history.append({"role": msg.role, "content": msg.content})
    return history


def _model_info() -> dict[str, Any]:
    """Return the simulated model descriptor."""
    full_name = f"{_MODEL_NAME}:{_MODEL_TAG}"
    return {
        "name": full_name,
        "model": full_name,
        "modified_at": "2024-01-01T00:00:00Z",
        "size": 0,
        "digest": "sha256:aurora_rag_emulated",
        "details": {
            "parent_model": "",
            "format": "aurora",
            "family": "rag",
            "families": ["rag"],
            "parameter_size": "N/A",
            "quantization_level": "N/A",
        },
    }


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/version")
async def ollama_version() -> dict[str, str]:
    """Return simulated Ollama version."""
    return {"version": "0.9.3"}


@router.get("/tags")
async def ollama_tags() -> dict[str, Any]:
    """Return the simulated model list."""
    return {"models": [_model_info()]}


@router.get("/ps")
async def ollama_running_models() -> dict[str, Any]:
    """Return currently running (loaded) models."""
    return {"models": [_model_info()]}


@router.post("/generate", response_model=None)
async def ollama_generate(
    req: OllamaGenerateRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> StreamingResponse | dict[str, Any]:
    """Text generation — pass-through to LLM, NOT routed through RAG.

    This endpoint is for raw text completion without retrieval augmentation.
    """
    try:
        if req.stream:
            return StreamingResponse(
                _stream_generate(req, service),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = await service.llm_generate(
            prompt=req.prompt, system=req.system, options=req.options
        )
        full_name = f"{_MODEL_NAME}:{_MODEL_TAG}"
        return {
            "model": full_name,
            "created_at": _now_iso(),
            "response": result["response"],
            "done": True,
            "total_duration": result.get("total_duration", 0),
            "prompt_eval_count": _count_tokens(req.prompt),
            "eval_count": _count_tokens(result["response"]),
        }
    except Exception as exc:
        logger.exception("Ollama generate failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat", response_model=None)
async def ollama_chat(
    req: OllamaChatRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> StreamingResponse | dict[str, Any]:
    """Chat with RAG routing based on message content prefix.

    The last user message is inspected for a mode prefix (``/local``,
    ``/global``, etc.) to select the retrieval strategy.  If the message
    matches the OpenWebUI chat_history pattern it is passed directly to
    the LLM without RAG.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    last_message = req.messages[-1]
    content = last_message.content

    # ── Determine mode and query ─────────────────────────────────────
    if _is_openwebui_passthrough(content):
        mode = "bypass"
        query_text = content
    else:
        mode, query_text = _parse_mode_and_query(content)

    # If after stripping prefix the query is empty, use original content
    if not query_text:
        query_text = content

    conversation_history = _build_conversation_history(req.messages)

    # ── Build system prompt if provided ──────────────────────────────
    system_prompt = req.system
    if system_prompt and conversation_history:
        if conversation_history[0]["role"] != "system":
            conversation_history.insert(
                0, {"role": "system", "content": system_prompt}
            )

    try:
        if req.stream:
            return StreamingResponse(
                _stream_chat(req, service, mode, query_text, conversation_history),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = await service.query(
            kb_name=_DEFAULT_KB,
            query=query_text,
            mode=mode,
            conversation_history=conversation_history,
            stream=False,
        )
        response_text = result.get("response", "")
        full_name = f"{_MODEL_NAME}:{_MODEL_TAG}"
        return {
            "model": full_name,
            "created_at": _now_iso(),
            "message": {"role": "assistant", "content": response_text},
            "done": True,
            "total_duration": result.get("total_duration", 0),
            "prompt_eval_count": _count_tokens(query_text),
            "eval_count": _count_tokens(response_text),
        }
    except Exception as exc:
        logger.exception("Ollama chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Streaming Generators ─────────────────────────────────────────────


async def _stream_generate(
    req: OllamaGenerateRequest,
    service: Any,
) -> AsyncGenerator[str, None]:
    """Stream raw LLM generation as NDJSON."""
    full_name = f"{_MODEL_NAME}:{_MODEL_TAG}"
    start = time.time()
    prompt_tokens = _count_tokens(req.prompt)
    full_response = ""

    try:
        result = await service.llm_generate(
            prompt=req.prompt, system=req.system, options=req.options, stream=True
        )
        stream_iter = result.get("stream_iterator")
        if stream_iter is not None:
            async for chunk in stream_iter:
                full_response += chunk
                yield json.dumps({
                    "model": full_name,
                    "created_at": _now_iso(),
                    "response": chunk,
                    "done": False,
                }) + "\n"
        else:
            full_response = result.get("response", "")
            yield json.dumps({
                "model": full_name,
                "created_at": _now_iso(),
                "response": full_response,
                "done": False,
            }) + "\n"

        elapsed_ns = int((time.time() - start) * 1_000_000_000)
        yield json.dumps({
            "model": full_name,
            "created_at": _now_iso(),
            "response": "",
            "done": True,
            "total_duration": elapsed_ns,
            "prompt_eval_count": prompt_tokens,
            "eval_count": _count_tokens(full_response),
        }) + "\n"
    except Exception as exc:
        yield json.dumps({"error": str(exc)}) + "\n"


async def _stream_chat(
    req: OllamaChatRequest,
    service: Any,
    mode: str,
    query_text: str,
    conversation_history: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream RAG chat response as NDJSON."""
    full_name = f"{_MODEL_NAME}:{_MODEL_TAG}"
    start = time.time()
    prompt_tokens = _count_tokens(query_text)
    full_response = ""

    try:
        result = await service.query(
            kb_name=_DEFAULT_KB,
            query=query_text,
            mode=mode,
            conversation_history=conversation_history,
            stream=True,
        )

        stream_iter = result.get("stream_iterator")
        if stream_iter is not None:
            async for chunk in stream_iter:
                full_response += chunk
                yield json.dumps({
                    "model": full_name,
                    "created_at": _now_iso(),
                    "message": {"role": "assistant", "content": chunk},
                    "done": False,
                }) + "\n"
        else:
            full_response = result.get("response", "")
            yield json.dumps({
                "model": full_name,
                "created_at": _now_iso(),
                "message": {"role": "assistant", "content": full_response},
                "done": False,
            }) + "\n"

        elapsed_ns = int((time.time() - start) * 1_000_000_000)
        yield json.dumps({
            "model": full_name,
            "created_at": _now_iso(),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "total_duration": elapsed_ns,
            "prompt_eval_count": prompt_tokens,
            "eval_count": _count_tokens(full_response),
        }) + "\n"
    except Exception as exc:
        yield json.dumps({
            "model": full_name,
            "created_at": _now_iso(),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "error": str(exc),
        }) + "\n"


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
