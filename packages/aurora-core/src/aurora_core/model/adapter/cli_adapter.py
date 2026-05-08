from __future__ import annotations

from typing import AsyncIterator, List

from aurora_core.model.base import BaseLLM
from aurora_core.model.local_cli import collapse_messages_for_cli, run_agent_stream
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig


class LocalCliLLM(BaseLLM):
    """LLM adapter backed by a locally installed coding CLI.

    The config maps as follows:
    - model_type: "daemon" or "cli"
    - api_base: agent id, for example "claude" or "codex"
    - model_name: optional CLI model override
    - extra.reasoning: optional reasoning effort for CLIs that expose it
    - extra.cwd: optional working directory for spawned process
    """

    @property
    def agent_id(self) -> str:
        return (self.config.api_base or self.config.extra.get("agent_id") or self.config.model_name).strip()

    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        text = ""
        finish_reason = "stop"
        async for chunk in self.achat_stream(messages, **kwargs):
            text += chunk.text or ""
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
        return ModelOutput(text=text, finish_reason=finish_reason)

    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        prompt = collapse_messages_for_cli(messages)
        model = self.config.extra.get("model") or self.config.model_name
        if model == self.agent_id:
            model = None
        reasoning = kwargs.get("reasoning") or self.config.extra.get("reasoning")
        cwd = kwargs.get("cwd") or self.config.extra.get("cwd")
        async for event in run_agent_stream(
            self.agent_id,
            prompt,
            cwd=cwd,
            model=model,
            reasoning=reasoning,
        ):
            event_type = event.get("type")
            if event_type == "text_delta":
                yield ModelOutput(text=str(event.get("delta") or ""))
            elif event_type == "thinking_delta":
                yield ModelOutput(text=str(event.get("delta") or ""), is_reasoning=True)
            elif event_type == "thinking_start":
                yield ModelOutput(
                    text="",
                    extra={"event_type": "status", "label": "thinking"},
                )
            elif event_type == "status":
                extra = {
                    "event_type": "status",
                    "label": event.get("label"),
                }
                if event.get("model") is not None:
                    extra["model"] = event.get("model")
                if event.get("detail") is not None:
                    extra["detail"] = event.get("detail")
                yield ModelOutput(
                    text="",
                    extra=extra,
                )
            elif event_type == "tool_use":
                yield ModelOutput(
                    text="",
                    extra={
                        "event_type": "tool_use",
                        "id": event.get("id"),
                        "name": event.get("name"),
                        "input": event.get("input"),
                    },
                )
            elif event_type == "tool_result":
                yield ModelOutput(
                    text="",
                    extra={
                        "event_type": "tool_result",
                        "toolUseId": event.get("toolUseId") or event.get("tool_use_id"),
                        "content": event.get("content"),
                        "isError": bool(event.get("isError") or event.get("is_error")),
                    },
                )
            elif event_type == "error":
                raise RuntimeError(str(event.get("message") or "CLI agent failed"))
        yield ModelOutput(text="", finish_reason="stop")
