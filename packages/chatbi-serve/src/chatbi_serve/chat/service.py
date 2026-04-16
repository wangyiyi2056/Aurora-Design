import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from chatbi_core.agent.skill.base import SkillRegistry
from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.chat.schema import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContentPart,
)


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

    async def _inject_skill_result(
        self, req: ChatRequest, messages: List[Message]
    ) -> List[Message]:
        if self.skill_registry is None:
            return messages
        skill_name = req.select_param or (
            req.ext_info.get("skill_name") if req.ext_info else None
        )
        if not skill_name:
            return messages
        try:
            skill = self.skill_registry.get(skill_name)
        except KeyError:
            return messages

        # Build context for skill execution
        # Try to find the last user message text
        user_text = ""
        for m in reversed(messages):
            if m.role == "user":
                content = m.content
                if isinstance(content, str):
                    user_text = content
                elif isinstance(content, list):
                    texts = [
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    user_text = "\n".join(texts)
                break

        # Try to find any attached file content in messages
        file_text = ""
        for m in messages:
            content = m.content
            if isinstance(content, list):
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "text"
                        and isinstance(item.get("text"), str)
                        and item["text"].startswith("[Attached file:")
                    ):
                        file_text += "\n" + item["text"]

        # CSV skill expects csv_content if available
        kwargs: Dict[str, Any] = {}
        if file_text:
            kwargs["csv_content"] = file_text
        try:
            result = await skill.execute(**kwargs)
        except Exception as e:
            result = f"Skill execution failed: {e}"

        system_msg = Message(
            role="system",
            content=f"You are using the skill '{skill_name}'. Here is the skill execution result:\n{result}",
        )
        return [system_msg] + messages

    async def chat(self, req: ChatRequest) -> ChatResponse:
        messages = self._build_messages(req)
        messages = await self._inject_skill_result(req, messages)

        user_text = ""
        for m in reversed(messages):
            if m.role == "user":
                content = m.content
                if isinstance(content, str):
                    user_text = content
                elif isinstance(content, list):
                    user_text = "\n".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    )
                break

        skill_name = req.select_param or (req.ext_info and req.ext_info.get("skill_name"))
        has_file = any(
            isinstance(m.content, list)
            and any(
                isinstance(item, dict) and item.get("type") == "file_url"
                for item in m.content
            )
            for m in messages
        )
        skip_sql = bool(skill_name or has_file)

        # Direct-return skills (visualization skills should not go through extra LLM)
        direct_return_skills = {"sql_chart", "sql_dashboard"}
        if skill_name in direct_return_skills and self.skill_registry:
            try:
                skill = self.skill_registry.get(skill_name)
            except KeyError:
                pass
            else:
                # Re-run skill with the original question text
                kwargs: Dict[str, Any] = {"question": user_text}
                result = await skill.execute(**kwargs)
                return ChatResponse(
                    id=f"chatbi-{int(time.time() * 1000)}",
                    created=int(time.time()),
                    model=skill_name,
                    choices=[
                        ChatChoice(
                            message=ChatMessage(role="assistant", content=result),
                            finish_reason="stop",
                        )
                    ],
                )

        if not skip_sql and self.sql_agent and self.sql_agent.is_sql_question(user_text):
            success, result = await self.sql_agent.run(user_text)
            content = result if success else f"SQL execution failed: {result}"
            return ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=int(time.time()),
                model="sql-agent",
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content=content),
                        finish_reason="stop",
                    )
                ],
            )

        llm = self._get_llm(req)
        output = await llm.achat(messages)
        return ChatResponse(
            id=f"chatbi-{int(time.time() * 1000)}",
            created=int(time.time()),
            model=llm.config.model_name,
            choices=[
                ChatChoice(
                    message=ChatMessage(role="assistant", content=output.text),
                    finish_reason=output.finish_reason,
                )
            ],
            usage=output.usage,
        )

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[str]:
        messages = self._build_messages(req)
        messages = await self._inject_skill_result(req, messages)

        # Direct-return skills for streaming (return single chunk)
        direct_return_skills = {"sql_chart", "sql_dashboard"}
        skill_name = req.select_param or (req.ext_info and req.ext_info.get("skill_name"))
        if skill_name in direct_return_skills and self.skill_registry:
            try:
                skill = self.skill_registry.get(skill_name)
            except KeyError:
                pass
            else:
                user_text = ""
                for m in reversed(messages):
                    if m.role == "user":
                        content = m.content
                        if isinstance(content, str):
                            user_text = content
                        elif isinstance(content, list):
                            user_text = "\n".join(
                                item.get("text", "")
                                for item in content
                                if isinstance(item, dict) and item.get("type") == "text"
                            )
                        break
                kwargs: Dict[str, Any] = {"question": user_text}
                result = await skill.execute(**kwargs)
                resp = ChatResponse(
                    id=f"chatbi-{int(time.time() * 1000)}",
                    created=int(time.time()),
                    model=skill_name,
                    choices=[
                        ChatChoice(
                            message=ChatMessage(role="assistant", content=result),
                            finish_reason="stop",
                        )
                    ],
                )
                yield f"data: {resp.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                return

        llm = self._get_llm(req)
        created = int(time.time())
        model_name = llm.config.model_name

        async for chunk in llm.achat_stream(messages):
            resp = ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=created,
                model=model_name,
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content=chunk.text),
                        finish_reason=chunk.finish_reason,
                    )
                ],
            )
            yield f"data: {resp.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
