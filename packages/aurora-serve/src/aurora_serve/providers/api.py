from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from urllib.parse import urlencode, urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aurora_core.model.local_cli import detect_agents, run_agent_stream

router = APIRouter(tags=["providers"])


class ProxyMessage(BaseModel):
    role: str
    content: str


class ProxyStreamRequest(BaseModel):
    baseUrl: str = ""
    apiKey: str = ""
    model: str
    systemPrompt: str | None = None
    messages: list[ProxyMessage] = Field(default_factory=list)
    maxTokens: int | None = None
    apiVersion: str | None = None


class RunCreateRequest(BaseModel):
    agentId: str
    message: str
    model: str | None = None
    reasoning: str | None = None
    cwd: str | None = None


@dataclass
class RunState:
    id: str
    agent_id: str
    status: str = "queued"
    events: list[tuple[int, str, dict[str, Any]]] = field(default_factory=list)
    task: asyncio.Task | None = None
    created_at: float = field(default_factory=time.time)
    next_event_id: int = 1

    def append(self, event: str, data: dict[str, Any]) -> None:
        self.events.append((self.next_event_id, event, data))
        self.next_event_id += 1


_RUNS: dict[str, RunState] = {}


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    return {"agents": await detect_agents()}


@router.post("/runs")
async def create_run(req: RunCreateRequest) -> dict[str, str]:
    run_id = str(uuid4())
    state = RunState(id=run_id, agent_id=req.agentId)
    _RUNS[run_id] = state
    state.task = asyncio.create_task(_run_cli_agent(state, req))
    return {"runId": run_id, "status": "queued"}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, after: int | None = None) -> StreamingResponse:
    state = _RUNS.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def stream() -> AsyncIterator[str]:
        cursor = after or 0
        while True:
            pending = [event for event in state.events if event[0] > cursor]
            for event_id, event, data in pending:
                cursor = event_id
                yield _sse(event, data, event_id=event_id)
            if state.status in {"succeeded", "failed", "canceled"} and cursor >= state.next_event_id - 1:
                break
            await asyncio.sleep(0.1)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict[str, str]:
    state = _RUNS.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if state.task and not state.task.done():
        state.task.cancel()
    state.status = "canceled"
    state.append("end", {"status": "canceled"})
    return {"status": "canceled"}


@router.post("/proxy/anthropic/stream")
async def proxy_anthropic(req: ProxyStreamRequest) -> StreamingResponse:
    _validate_proxy_req(req, require_base_url=True)
    url = _append_versioned_path(req.baseUrl, "/messages")
    payload: dict[str, Any] = {
        "model": req.model,
        "max_tokens": req.maxTokens if req.maxTokens and req.maxTokens > 0 else 8192,
        "messages": [message.model_dump() for message in req.messages],
        "stream": True,
    }
    if req.systemPrompt:
        payload["system"] = req.systemPrompt
    headers = {
        "Content-Type": "application/json",
        "x-api-key": req.apiKey,
        "anthropic-version": "2023-06-01",
    }
    return StreamingResponse(
        _proxy_stream(req.model, url, payload, headers, _extract_anthropic_delta),
        media_type="text/event-stream",
    )


@router.post("/proxy/openai/stream")
async def proxy_openai(req: ProxyStreamRequest) -> StreamingResponse:
    _validate_proxy_req(req, require_base_url=True)
    url = _append_versioned_path(req.baseUrl, "/chat/completions")
    messages = [message.model_dump() for message in req.messages]
    if req.systemPrompt:
        messages.insert(0, {"role": "system", "content": req.systemPrompt})
    payload = {
        "model": req.model,
        "messages": messages,
        "max_tokens": req.maxTokens if req.maxTokens and req.maxTokens > 0 else 8192,
        "stream": True,
    }
    return StreamingResponse(
        _proxy_stream(
            req.model,
            url,
            payload,
            {"Content-Type": "application/json", "Authorization": f"Bearer {req.apiKey}"},
            _extract_openai_delta,
        ),
        media_type="text/event-stream",
    )


@router.post("/proxy/azure/stream")
async def proxy_azure(req: ProxyStreamRequest) -> StreamingResponse:
    _validate_proxy_req(req, require_base_url=True)
    base = req.baseUrl.rstrip("/")
    version = req.apiVersion.strip() if req.apiVersion else "2024-10-21"
    query = urlencode({"api-version": version})
    url = f"{base}/openai/deployments/{req.model}/chat/completions?{query}"
    messages = [message.model_dump() for message in req.messages]
    if req.systemPrompt:
        messages.insert(0, {"role": "system", "content": req.systemPrompt})
    payload = {
        "messages": messages,
        "max_tokens": req.maxTokens if req.maxTokens and req.maxTokens > 0 else 8192,
        "stream": True,
    }
    return StreamingResponse(
        _proxy_stream(
            req.model,
            url,
            payload,
            {"Content-Type": "application/json", "api-key": req.apiKey},
            _extract_openai_delta,
        ),
        media_type="text/event-stream",
    )


@router.post("/proxy/google/stream")
async def proxy_google(req: ProxyStreamRequest) -> StreamingResponse:
    if not req.apiKey or not req.model:
        raise HTTPException(status_code=400, detail="apiKey and model are required")
    base_url = req.baseUrl or "https://generativelanguage.googleapis.com"
    _validate_base_url(base_url)
    url = f"{base_url.rstrip('/')}/v1beta/models/{req.model}:streamGenerateContent?alt=sse"
    contents = [
        {
            "role": "model" if message.role == "assistant" else "user",
            "parts": [{"text": message.content}],
        }
        for message in req.messages
    ]
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": req.maxTokens if req.maxTokens and req.maxTokens > 0 else 8192
        },
    }
    if req.systemPrompt:
        payload["systemInstruction"] = {"parts": [{"text": req.systemPrompt}]}
    return StreamingResponse(
        _proxy_stream(
            req.model,
            url,
            payload,
            {"Content-Type": "application/json", "x-goog-api-key": req.apiKey},
            _extract_gemini_delta,
        ),
        media_type="text/event-stream",
    )


async def _run_cli_agent(state: RunState, req: RunCreateRequest) -> None:
    state.status = "running"
    state.append("start", {"runId": state.id, "agentId": req.agentId, "model": req.model})
    try:
        async for event in run_agent_stream(
            req.agentId,
            req.message,
            cwd=req.cwd,
            model=req.model,
            reasoning=req.reasoning,
        ):
            if event.get("type") == "stderr":
                state.append("stderr", {"chunk": event.get("chunk", "")})
            elif event.get("type") == "error":
                state.status = "failed"
                state.append("error", {"error": {"code": "AGENT_ERROR", "message": event.get("message")}})
            else:
                state.append("agent", event)
        if state.status != "failed":
            state.status = "succeeded"
        state.append("end", {"status": state.status})
    except asyncio.CancelledError:
        state.status = "canceled"
        state.append("end", {"status": "canceled"})
    except Exception as exc:
        state.status = "failed"
        state.append("error", {"error": {"code": "INTERNAL_ERROR", "message": str(exc)}})
        state.append("end", {"status": "failed"})


async def _proxy_stream(
    model: str,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    extractor,
) -> AsyncIterator[str]:
    yield _sse("start", {"model": model})
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code >= 400:
                    text = await resp.aread()
                    yield _sse(
                        "error",
                        {
                            "error": {
                                "code": _proxy_error_code(resp.status_code),
                                "message": f"Upstream error: {resp.status_code}",
                                "details": text.decode("utf-8", errors="replace"),
                            }
                        },
                    )
                    return
                async for event_payload in _iter_sse_payloads(resp):
                    if event_payload == "[DONE]":
                        yield _sse("end", {})
                        return
                    try:
                        data = json.loads(event_payload)
                    except json.JSONDecodeError:
                        continue
                    stream_error = _extract_stream_error(data)
                    if stream_error:
                        yield _sse("error", {"error": {"code": "UPSTREAM_ERROR", "message": stream_error}})
                        return
                    delta = extractor(data)
                    if isinstance(delta, dict):
                        event = str(delta.get("event") or "delta")
                        text = str(delta.get("delta") or "")
                        if text:
                            yield _sse(event, {"delta": text})
                    elif delta:
                        yield _sse("delta", {"delta": delta})
        yield _sse("end", {})
    except Exception as exc:
        yield _sse("error", {"error": {"code": "INTERNAL_ERROR", "message": str(exc)}})


async def _iter_sse_payloads(resp: httpx.Response) -> AsyncIterator[str]:
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        yield line[5:].lstrip()


def _validate_proxy_req(req: ProxyStreamRequest, *, require_base_url: bool) -> None:
    if require_base_url and not req.baseUrl:
        raise HTTPException(status_code=400, detail="baseUrl is required")
    if not req.apiKey or not req.model:
        raise HTTPException(status_code=400, detail="apiKey and model are required")
    _validate_base_url(req.baseUrl)


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid baseUrl")
    hostname = parsed.hostname or ""
    if hostname in {"0.0.0.0", "::"}:
        raise HTTPException(status_code=403, detail="Forbidden baseUrl")


def _append_versioned_path(base_url: str, path: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/v1"):
        return f"{clean}{path}"
    return f"{clean}/v1{path}"


def _sse(event: str, data: dict[str, Any], *, event_id: int | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_anthropic_delta(data: dict[str, Any]) -> str:
    if data.get("type") == "content_block_delta":
        delta = data.get("delta") or {}
        return str(delta.get("text") or "")
    return ""


def _extract_openai_delta(data: dict[str, Any]) -> str | dict[str, str]:
    choices = data.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if content:
        return str(content)
    reasoning = delta.get("reasoning_content")
    if reasoning:
        return {"event": "reasoning_delta", "delta": str(reasoning)}
    return ""


def _extract_gemini_delta(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    parts = ((candidates[0] if candidates else {}).get("content") or {}).get("parts") or []
    return "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))


def _extract_stream_error(data: dict[str, Any]) -> str | None:
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "Provider error")
    if isinstance(data.get("message"), str) and data.get("type") == "error":
        return str(data["message"])
    return None


def _proxy_error_code(status_code: int) -> str:
    if status_code in {401, 403}:
        return "AUTH_ERROR"
    if status_code == 429:
        return "RATE_LIMIT"
    if status_code >= 500:
        return "UPSTREAM_UNAVAILABLE"
    return "UPSTREAM_ERROR"
