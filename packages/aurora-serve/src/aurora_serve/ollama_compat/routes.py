"""Ollama-compatible API routes.

Provides a drop-in shim so that Ollama-aware clients (Open WebUI,
Continue, etc.) can talk to the Aurora RAG knowledge base.

Mounted at ``/api`` (NOT ``/api/v1``) for Ollama client compatibility.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from aurora_serve.ollama_compat.config import get_config
from aurora_serve.ollama_compat.mapper import (
    build_conversation_history,
    count_tokens,
    inject_system_into_history,
    is_openwebui_passthrough,
    parse_mode_and_query,
)
from aurora_serve.ollama_compat.models import (
    OllamaChatRequest,
    OllamaGenerateRequest,
    OllamaModelDetails,
    OllamaModelInfo,
    OllamaShowRequest,
    OllamaShowResponse,
    OllamaTagsResponse,
    OllamaVersionResponse,
)
from aurora_serve.ollama_compat.streaming import (
    now_iso,
    stream_chat_response,
    stream_generate_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ollama"])


# ── Dependency ──────────────────────────────────────────────────────


def _get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Helpers ─────────────────────────────────────────────────────────


def _model_info(config: Any = None) -> OllamaModelInfo:
    """Build the simulated model descriptor."""
    cfg = config or get_config()
    full_name = cfg.full_model_name
    return OllamaModelInfo(
        name=full_name,
        model=full_name,
        modified_at="2024-01-01T00:00:00Z",
        size=0,
        digest="sha256:aurora_rag_emulated",
        details=OllamaModelDetails(),
    )


def _build_model_list(config: Any = None) -> list[OllamaModelInfo]:
    """Build a model list from all configured model names."""
    cfg = config or get_config()
    models: list[OllamaModelInfo] = []
    for name in cfg.list_models():
        tag = cfg.default_tag
        full_name = f"{name}:{tag}"
        models.append(
            OllamaModelInfo(
                name=full_name,
                model=full_name,
                modified_at="2024-01-01T00:00:00Z",
                size=0,
                digest=f"sha256:aurora_rag_{name}",
                details=OllamaModelDetails(),
            )
        )
    return models


# ── Endpoints: Model Management ─────────────────────────────────────


@router.get("/version", response_model=OllamaVersionResponse)
async def ollama_version() -> OllamaVersionResponse:
    """Return simulated Ollama version."""
    return OllamaVersionResponse(version="0.9.3")


@router.get("/tags", response_model=OllamaTagsResponse)
async def ollama_tags() -> OllamaTagsResponse:
    """Return the simulated model list (``GET /api/tags``)."""
    return OllamaTagsResponse(models=_build_model_list())


@router.get("/ps")
async def ollama_running_models() -> dict[str, Any]:
    """Return currently running (loaded) models (``GET /api/ps``)."""
    return {"models": [m.model_dump() for m in _build_model_list()]}


@router.post("/show", response_model=OllamaShowResponse)
async def ollama_show(req: OllamaShowRequest) -> OllamaShowResponse:
    """Show model information (``POST /api/show``).

    Open WebUI calls this to display model details.
    """
    cfg = get_config()
    bare = req.name.split(":")[0] if ":" in req.name else req.name
    known = cfg.list_models()

    if bare not in known:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{req.name}' not found. Available: {known}",
        )

    kb_name = cfg.resolve_kb(bare)
    return OllamaShowResponse(
        license="MIT",
        modelfile=(
            f"# Aurora RAG model: {bare}\n"
            f"# Routes queries to knowledge base: {kb_name}\n"
            f"FROM aurora\n"
            f"PARAMETER knowledge_base {kb_name}\n"
        ),
        parameters=(
            f"knowledge_base: {kb_name}\n"
            f"retrieval_mode: mix\n"
            f"stream: true\n"
        ),
        template="{{ .System }}\n{{ .Prompt }}",
        details=OllamaModelDetails(),
    )


# ── Endpoints: Chat ─────────────────────────────────────────────────


@router.post("/chat", response_model=None)
async def ollama_chat(
    req: OllamaChatRequest,
    service: Any = Depends(_get_knowledge_v2_service),
) -> StreamingResponse | dict[str, Any]:
    """Chat with RAG routing based on message content prefix.

    The last user message is inspected for a mode prefix (``/local``,
    ``/global``, etc.) to select the retrieval strategy.  If the message
    matches the OpenWebUI ``chat_history`` pattern it is passed directly
    to the LLM without RAG.
    """
    cfg = get_config()

    if not req.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    last_message = req.messages[-1]
    content = last_message.content

    # ── Determine mode, query, and KB ────────────────────────────────
    if is_openwebui_passthrough(content):
        mode = "bypass"
        query_text = content
    else:
        mode, query_text = parse_mode_and_query(content)

    # If stripping the prefix left an empty string, use original content
    if not query_text:
        query_text = content

    conversation_history = build_conversation_history(req.messages)
    conversation_history = inject_system_into_history(
        conversation_history, req.system
    )

    kb_name = cfg.resolve_kb(req.model)
    model_name = cfg.full_model_name

    # ── Stream or block ──────────────────────────────────────────────
    try:
        if req.stream:
            return StreamingResponse(
                _do_stream_chat(
                    service, kb_name, query_text, mode,
                    conversation_history, model_name,
                ),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = await service.query(
            kb_name=kb_name,
            query=query_text,
            mode=mode,
            conversation_history=conversation_history,
            stream=False,
        )
        response_text = result.get("response", "")
        return {
            "model": model_name,
            "created_at": now_iso(),
            "message": {"role": "assistant", "content": response_text},
            "done": True,
            "total_duration": result.get("total_duration", 0),
            "prompt_eval_count": count_tokens(query_text),
            "eval_count": count_tokens(response_text),
        }
    except Exception as exc:
        logger.exception("Ollama chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _do_stream_chat(
    service: Any,
    kb_name: str,
    query_text: str,
    mode: str,
    conversation_history: list[dict[str, str]],
    model_name: str,
):
    """Inner generator that calls service.query and streams NDJSON."""
    result = await service.query(
        kb_name=kb_name,
        query=query_text,
        mode=mode,
        conversation_history=conversation_history,
        stream=True,
    )
    async for line in stream_chat_response(result, model_name, query_text):
        yield line


# ── Endpoints: Generate ─────────────────────────────────────────────


@router.post("/generate", response_model=None)
async def ollama_generate(
    req: OllamaGenerateRequest,
    service: Any = Depends(_get_knowledge_v2_service),
) -> StreamingResponse | dict[str, Any]:
    """Text generation — pass-through to LLM, NOT routed through RAG.

    This endpoint is for raw text completion without retrieval augmentation.
    """
    cfg = get_config()
    model_name = cfg.full_model_name

    try:
        if req.stream:
            return StreamingResponse(
                _do_stream_generate(service, req, model_name),
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
        return {
            "model": model_name,
            "created_at": now_iso(),
            "response": result["response"],
            "done": True,
            "total_duration": result.get("total_duration", 0),
            "prompt_eval_count": count_tokens(req.prompt),
            "eval_count": count_tokens(result["response"]),
        }
    except Exception as exc:
        logger.exception("Ollama generate failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _do_stream_generate(
    service: Any,
    req: OllamaGenerateRequest,
    model_name: str,
):
    """Inner generator that calls service.llm_generate and streams NDJSON."""
    result = await service.llm_generate(
        prompt=req.prompt, system=req.system, options=req.options, stream=True
    )
    async for line in stream_generate_response(result, model_name, req.prompt):
        yield line
