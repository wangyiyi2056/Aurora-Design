from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, List

import httpx

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig


class GoogleLLM(BaseLLM):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("GOOGLE_API_KEY") or ""
        self.base_url = (config.api_base or "https://generativelanguage.googleapis.com").rstrip("/")

    def _build_payload(self, messages: List[Message], stream: bool) -> tuple[str, dict[str, Any]]:
        system_parts: list[dict[str, str]] = []
        contents: list[dict[str, Any]] = []
        for message in messages:
            text = message.content if isinstance(message.content, str) else json.dumps(message.content, ensure_ascii=False)
            if message.role == "system":
                system_parts.append({"text": text})
                continue
            contents.append({
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": text}],
            })
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": self.config.max_tokens or 8192},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        suffix = ":streamGenerateContent?alt=sse" if stream else ":generateContent"
        url = f"{self.base_url}/v1beta/models/{self.config.model_name}{suffix}"
        return url, payload

    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        url, payload = self._build_payload(messages, stream=False)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        return ModelOutput(text=_extract_text(data), finish_reason="stop")

    async def achat_stream(self, messages: List[Message], **kwargs) -> AsyncIterator[ModelOutput]:
        url, payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].lstrip())
                    except json.JSONDecodeError:
                        continue
                    text = _extract_text(data)
                    if text:
                        yield ModelOutput(text=text)
        yield ModelOutput(text="", finish_reason="stop")


def _extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    parts = ((candidates[0] if candidates else {}).get("content") or {}).get("parts") or []
    return "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
