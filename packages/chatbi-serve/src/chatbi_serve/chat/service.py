import json
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from chatbi_core.agent.skill.base import SkillRegistry
from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ToolCall
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.chat.schema import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContentPart,
)


SYSTEM_TOOL_PROMPT = """You are ChatBI, an intelligent data assistant. You have access to the following tools. Use them when appropriate to answer user questions accurately."""


class ChatService:
    def __init__(
        self,
        model_registry: ModelRegistry,
        sql_agent: Optional["SQLAgent"] = None,
        skill_registry: Optional[SkillRegistry] = None,
    ):
        self.registry = model_registry
        self.sql_agent = sql_agent
        self.skill_registry = skill_registry

    def _get_llm(self, req: ChatRequest) -> OpenAILLM:
        if req.model_config_field:
            cfg = LLMConfig(
                model_name=req.model_config_field.model_name,
                model_type="openai",
                api_base=req.model_config_field.base_url,
                api_key=req.model_config_field.api_key,
            )
            return OpenAILLM(cfg)
        return self.registry.get_llm(req.model)

    def _resolve_content_parts(
        self, content: Union[str, List[ContentPart]]
    ) -> Union[str, List[Dict[str, Any]]]:
        if isinstance(content, str):
            return content
        resolved: List[Dict[str, Any]] = []
        for part in content:
            if part.type == "text" and part.text is not None:
                resolved.append({"type": "text", "text": part.text})
            elif part.type == "image_url" and part.image_url is not None:
                resolved.append(
                    {"type": "image_url", "image_url": {"url": part.image_url.url}}
                )
            elif part.type == "file_url" and part.file_url is not None:
                file_path = Path(part.file_url.url)
                if file_path.exists():
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                else:
                    text = f"[File not found: {part.file_url.url}]"
                resolved.append(
                    {
                        "type": "text",
                        "text": f"[Attached file: {part.file_url.file_name}]\n{text}",
                    }
                )
        return resolved

    def _build_messages(self, req: ChatRequest) -> List[Message]:
        messages: List[Message] = []
        for m in req.messages:
            resolved = self._resolve_content_parts(m.content)
            messages.append(Message(role=m.role, content=resolved))
        return messages

    def _build_tools(self) -> List[Dict[str, Any]] | None:
        if not self.skill_registry:
            return None
        skills = self.skill_registry.list_skills()
        if not skills:
            return None
        tools: List[Dict[str, Any]] = []
        for name in skills:
            skill = self.skill_registry.get(name)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": skill.name,
                        "description": skill.description,
                        "parameters": skill.parameters,
                    },
                }
            )
        return tools

    async def _execute_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[Message]:
        if not self.skill_registry:
            return []
        tool_messages: List[Message] = []
        for tc in tool_calls:
            if tc.type != "function":
                continue
            fn_name = tc.function.get("name", "")
            fn_args = tc.function.get("arguments", "{}")
            try:
                skill = self.skill_registry.get(fn_name)
            except KeyError:
                result = f"Tool '{fn_name}' not found."
            else:
                try:
                    args = json.loads(fn_args) if fn_args else {}
                    result = await skill.execute(**args)
                except Exception as e:
                    result = f"Tool execution failed: {e}"
            tool_messages.append(
                Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=tc.id,
                    name=fn_name,
                )
            )
        return tool_messages

    async def chat(self, req: ChatRequest) -> ChatResponse:
        messages = self._build_messages(req)

        # Inject system prompt with tool instructions if tools are available
        tools = self._build_tools()
        if tools and (not messages or messages[0].role != "system"):
            messages.insert(
                0,
                Message(
                    role="system",
                    content=SYSTEM_TOOL_PROMPT,
                ),
            )

        llm = self._get_llm(req)
        max_tool_rounds = 5

        for _ in range(max_tool_rounds):
            output = await llm.achat(
                messages,
                tools=tools,
                tool_choice="auto",
            )

            if output.finish_reason == "tool_calls" and output.tool_calls:
                # Append assistant message with tool_calls
                messages.append(
                    Message(
                        role="assistant",
                        content=output.text,
                        tool_calls=output.tool_calls,
                    )
                )
                # Execute tools and append results
                tool_results = await self._execute_tool_calls(output.tool_calls)
                messages.extend(tool_results)
                continue

            # Final answer
            return ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=int(time.time()),
                model=llm.config.model_name,
                choices=[
                    ChatChoice(
                        message=ChatMessage(
                            role="assistant", content=output.text
                        ),
                        finish_reason=output.finish_reason,
                    )
                ],
                usage=output.usage,
            )

        # Fallback if too many rounds
        return ChatResponse(
            id=f"chatbi-{int(time.time() * 1000)}",
            created=int(time.time()),
            model=llm.config.model_name,
            choices=[
                ChatChoice(
                    message=ChatMessage(
                        role="assistant",
                        content="Reached maximum tool calling rounds.",
                    ),
                    finish_reason="stop",
                )
            ],
        )

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[str]:
        messages = self._build_messages(req)
        tools = self._build_tools()

        if tools and (not messages or messages[0].role != "system"):
            messages.insert(
                0,
                Message(
                    role="system",
                    content=SYSTEM_TOOL_PROMPT,
                ),
            )

        llm = self._get_llm(req)

        # Fallback to non-streaming when tools are involved
        # because aggregating streaming tool_calls is complex
        if tools:
            max_tool_rounds = 5
            for _ in range(max_tool_rounds):
                output = await llm.achat(
                    messages,
                    tools=tools,
                    tool_choice="auto",
                )
                if output.finish_reason == "tool_calls" and output.tool_calls:
                    messages.append(
                        Message(
                            role="assistant",
                            content=output.text,
                            tool_calls=output.tool_calls,
                        )
                    )
                    tool_results = await self._execute_tool_calls(output.tool_calls)
                    messages.extend(tool_results)
                    continue

                resp = ChatResponse(
                    id=f"chatbi-{int(time.time() * 1000)}",
                    created=int(time.time()),
                    model=llm.config.model_name,
                    choices=[
                        ChatChoice(
                            message=ChatMessage(
                                role="assistant", content=output.text
                            ),
                            finish_reason=output.finish_reason,
                        )
                    ],
                    usage=output.usage,
                )
                yield f"data: {resp.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                return

            resp = ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=int(time.time()),
                model=llm.config.model_name,
                choices=[
                    ChatChoice(
                        message=ChatMessage(
                            role="assistant",
                            content="Reached maximum tool calling rounds.",
                        ),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {resp.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            return

        created = int(time.time())
        model_name = llm.config.model_name

        async for chunk in llm.achat_stream(messages):
            resp = ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=created,
                model=model_name,
                choices=[
                    ChatChoice(
                        message=ChatMessage(
                            role="assistant", content=chunk.text
                        ),
                        finish_reason=chunk.finish_reason,
                    )
                ],
            )
            yield f"data: {resp.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
