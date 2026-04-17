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

CSV_CHART_PROMPT = """
When you have analyzed CSV data and want to present a visualization, you MUST output a ```vis-db-chart code block with the following JSON structure:

```vis-db-chart
{"type": "response_bar_chart", "title": "Chart Title", "data": [{"column1": "value1", "column2": 123}, ...]}
```

Available chart types:
- response_table: suitable for display with many columns or non-numeric columns
- response_bar_chart: used to compare values across categories
- response_line_chart: used to display trend analysis over time or sequence
- response_pie_chart: suitable for proportion and distribution (few categories, 2-8)
- response_scatter_chart: suitable for exploring relationships between variables
- response_area_chart: suitable for time series data with filled areas

Important:
1. Use the actual column names from the CSV data as keys in the data array
2. Choose the chart type based on data characteristics (time series → line, comparison → bar, proportion → pie)
3. For pie charts, use {"name": "category", "value": number} format in data
4. Always include a meaningful title that describes what the chart shows
"""


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
    ) -> tuple[List[Message], bool]:
        """Execute tool calls and return messages plus flag indicating if csv_analysis was used."""
        if not self.skill_registry:
            return [], False
        tool_messages: List[Message] = []
        used_csv_analysis = False
        for tc in tool_calls:
            if tc.type != "function":
                continue
            fn_name = tc.function.get("name", "")
            fn_args = tc.function.get("arguments", "{}")
            if fn_name == "csv_analysis":
                used_csv_analysis = True
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
        return tool_messages, used_csv_analysis

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
                tool_results, used_csv_analysis = await self._execute_tool_calls(output.tool_calls)
                messages.extend(tool_results)
                # If csv_analysis was used, append chart prompt to guide LLM
                if used_csv_analysis:
                    messages.append(
                        Message(
                            role="system",
                            content=CSV_CHART_PROMPT,
                        )
                    )
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
                    tool_results, used_csv_analysis = await self._execute_tool_calls(output.tool_calls)
                    messages.extend(tool_results)
                    if used_csv_analysis:
                        messages.append(
                            Message(
                                role="system",
                                content=CSV_CHART_PROMPT,
                            )
                        )
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
