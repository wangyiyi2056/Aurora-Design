"""Enhanced Chat Service with Claude Code architecture."""

import json
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from chatbi_core.agent.skill.base import SkillRegistry
from chatbi_core.session import SessionManager, SessionMessage, Session
from chatbi_core.memory import MemoryManager, MemoryType
from chatbi_core.hooks import HookManager, HookType
from chatbi_core.context import ContextCompactor, ToolSearchManager, ContextMonitor
from chatbi_core.subagents import SubagentManager, SubagentDefinition
from chatbi_core.permissions import PermissionManager, PermissionMode
from chatbi_core.mcp.client import MCPClient
from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.model.adapter.anthropic_adapter import AnthropicLLM
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

# Status system (ported from Claude Code)
from chatbi_core.status import CostTracker

# Prompt system (ported from Claude Code)
from chatbi_core.prompt import (
    PromptBuilder,
    ContextProvider,
    build_system_prompt,
    build_system_prompt_block,
    DYNAMIC_BOUNDARY,
)

# New tool system imports
from chatbi_core.tool import (
    Tool,
    ToolRegistry,
    ToolUseContext,
    ToolPermissionContext,
    ToolResult,
    build_tool,
    find_tool_by_name,
    filter_tools_by_deny_rules,
    assemble_tool_pool,
    get_all_base_tools,
    get_tools,
    get_merged_tools,
    run_tool_use,
    run_tools,
    StreamingToolExecutor,
)

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


class EnhancedChatService:
    """Enhanced Chat Service with Claude Code architecture components.

    Integrates:
    - Session Management (persistence, resume, fork)
    - Memory System (auto-save preferences, project context)
    - Hooks System (lifecycle hooks)
    - Context Compaction (automatic context management)
    - Tool Search (on-demand tool loading)
    - Subagents (parallel task execution)
    - Permissions (multi-level permission control)
    - MCP (Model Context Protocol tool integration)
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        sql_agent: Optional["SQLAgent"] = None,
        skill_registry: Optional[SkillRegistry] = None,
        project_path: Optional[str] = None,
        mcp_client: Optional["MCPClient"] = None,
    ):
        self.registry = model_registry
        self.sql_agent = sql_agent
        self.skill_registry = skill_registry
        self.mcp_client = mcp_client

        # Initialize Claude Code architecture components
        self.session_manager = SessionManager()

        # Build proper paths for project-level configs
        project_settings_file = None
        if project_path:
            project_settings_file = str(Path(project_path) / ".chatbi" / "settings.json")

        self.memory_manager = MemoryManager(project_path=project_path)
        self.hook_manager = HookManager(project_settings_path=project_settings_file)
        self.context_compactor = ContextCompactor()
        self.context_monitor = ContextMonitor(max_tokens=200000)
        self.tool_search = ToolSearchManager()

        project_agents_path = str(Path(project_path) / ".chatbi" / "agents") if project_path else None
        self.subagent_manager = SubagentManager(agents_path=project_agents_path)
        self.permission_manager = PermissionManager(project_settings_path=project_settings_file)

        # Initialize the new ToolRegistry (ported from Claude Code)
        self.tool_registry = ToolRegistry()

        # Initialize CostTracker (ported from Claude Code)
        self.cost_tracker = CostTracker()

        # Initialize PromptBuilder (ported from Claude Code)
        self.prompt_builder = PromptBuilder(
            context_provider=ContextProvider(
                project_root=project_path or str(Path.cwd()),
                memory_manager=self.memory_manager,
                skill_registry=skill_registry,
            ),
            skill_registry=skill_registry,
            memory_manager=self.memory_manager,
            include_chart_vis=True,
        )

        # Register built-in tools (Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent)
        for tool in get_all_base_tools():
            self.tool_registry.register(tool)

        # Register skills as tools in the registry
        if skill_registry:
            for name in skill_registry.list_skills():
                skill = skill_registry.get(name)
                # Create a Tool wrapper from each skill
                skill_tool = build_tool(
                    name=skill.name,
                    description=skill.description,
                    input_schema=skill.parameters,
                    call_fn=skill.execute,
                    is_read_only_fn=lambda _: True,
                )
                self.tool_registry.register(skill_tool)

                self.tool_search.register_tool(
                    name=skill.name,
                    description=skill.description,
                    parameters=skill.parameters,
                    source="builtin",
                )

        # Register MCP tools to tool registry and search
        if mcp_client:
            for tool in mcp_client.get_tools():
                mcp_tool = build_tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    is_mcp=True,
                )
                self.tool_registry.register_mcp(mcp_tool)

                self.tool_search.register_tool(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.input_schema,
                    source="mcp",
                )

    async def start_session(self, project_path: str = "") -> Session:
        """Start a new session with memory context."""
        # Run session start hooks
        await self.hook_manager.run_session_start()

        # Create session
        session = self.session_manager.create_session(
            project_path=project_path,
        )

        # Load memory context
        memory_context = self.memory_manager.get_memory_context()

        return session

    def _get_llm(self, req: ChatRequest) -> Union[OpenAILLM, AnthropicLLM]:
        """Get LLM for request."""
        if req.model_config_field:
            model_type = req.model_config_field.model_type or "openai"
            cfg = LLMConfig(
                model_name=req.model_config_field.model_name,
                model_type=model_type,
                api_base=req.model_config_field.base_url,
                api_key=req.model_config_field.api_key,
            )
            if model_type == "anthropic":
                return AnthropicLLM(cfg)
            return OpenAILLM(cfg)
        return self.registry.get_llm(req.model)

    def _resolve_content_parts(
        self, content: Union[str, List[ContentPart]]
    ) -> Union[str, List[Dict[str, Any]]]:
        """Resolve content parts."""
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
        """Build messages from request."""
        messages: List[Message] = []
        for m in req.messages:
            resolved = self._resolve_content_parts(m.content)
            messages.append(Message(role=m.role, content=resolved))
        return messages

    def _build_tools(self) -> List[Dict[str, Any]] | None:
        """Build tools for LLM using the new tool registry."""
        # Get active tools from the registry
        tools = self.tool_registry.get_active_tools()
        if not tools:
            return None

        # Convert to OpenAI function-calling format
        result = []
        for t in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            })

        return result

    async def _execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
    ) -> tuple[List[Message], bool]:
        """Execute tool calls using the new Tool system."""
        if not self.tool_registry:
            return [], False

        tool_messages: List[Message] = []
        used_csv_analysis = False

        # Build ToolUseContext
        context = ToolUseContext(
            options={
                "tools": self.tool_registry.get_active_tools(),
                "skill_registry": self.skill_registry,
                "subagent_manager": self.subagent_manager,
                "mcp_client": self.mcp_client,
                "hook_manager": self.hook_manager,
                "permission_manager": self.permission_manager,
                "session_id": session_id,
            },
        )

        # Convert ToolCall blocks to the format expected by the executor
        tool_blocks = []
        for tc in tool_calls:
            if tc.type != "function":
                continue
            try:
                args = json.loads(tc.function.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_blocks.append({
                "name": tc.function.get("name", ""),
                "id": tc.id,
                "input": args,
            })

        if not tool_blocks:
            return [], False

        # Execute tools using run_tools (with concurrency control)
        assistant_msg_uuid = f"assistant-{int(time.time() * 1000)}"
        async for update in run_tools(
            tool_blocks,
            self.tool_registry.get_active_tools(),
            assistant_message_uuid=assistant_msg_uuid,
            context=context,
        ):
            if update.message is None:
                continue

            msg = update.message
            content_str = ""
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict):
                        content_str += part.get("content", "")
                if not content_str:
                    content_str = json.dumps(msg["content"])
            else:
                content_str = str(msg.get("content", ""))

            # Track csv_analysis
            if "csv_analysis" in content_str:
                used_csv_analysis = True

            # Build tool result
            tool_msg = Message(
                role="tool",
                content=content_str,
                tool_call_id=msg.get("tool_use_id", ""),
                name=msg.get("name", ""),
            )
            tool_messages.append(tool_msg)

            # Record tool call in cost tracker
            if msg.get("name"):
                has_error = "error" in content_str.lower()
                self.cost_tracker.record_tool_call(
                    success=not has_error,
                    duration_ms=0,
                )

            # Run PostToolUse hooks
            if msg.get("name"):
                await self.hook_manager.run_post_tool_use(
                    tool_name=msg["name"],
                    output_data=content_str,
                )

            # Save to session
            if session_id and msg.get("name"):
                self.session_manager.append_message(
                    session_id,
                    SessionMessage(
                        type="tool_result",
                        content=content_str,
                        role="tool",
                        tool_call_id=msg.get("tool_use_id", ""),
                        tool_name=msg.get("name", ""),
                    ),
                )

        return tool_messages, used_csv_analysis

    async def chat(
        self,
        req: ChatRequest,
        session_id: Optional[str] = None,
    ) -> ChatResponse:
        """Chat with enhanced features."""
        # Start session if needed
        if not session_id:
            session = await self.start_session()
            session_id = session.id

        messages = self._build_messages(req)

        # Add memory context as system message
        memory_context = self.memory_manager.get_memory_context()
        if memory_context:
            messages.insert(
                0,
                Message(role="system", content=memory_context),
            )

        # Build system prompt using PromptBuilder (Claude Code architecture)
        model_type = req.model_config_field.model_type if req.model_config_field else "openai"
        tools = None
        if model_type not in ("anthropic", "kimi"):
            tools = self._build_tools()
        if tools and (not messages or messages[0].role != "system"):
            system_prompt = self.prompt_builder.build_single_string()
            messages.insert(
                0,
                Message(role="system", content=system_prompt),
            )

        # Inject user context (CLAUDE.md + date) as <system-reminder> user message
        user_context = self.prompt_builder.get_user_context()
        if user_context:
            messages.insert(
                0,
                Message(role="user", content=f"<system-reminder>\n{user_context}\n</system-reminder>"),
            )

        # Inject system context (git status) to system prompt
        system_context = self.prompt_builder.get_system_context()
        if system_context and messages and messages[0].role == "system":
            messages[0] = Message(
                role="system",
                content=messages[0].content + "\n\n" + system_context,
            )

        # Save user message to session
        if messages:
            last_user = None
            for m in reversed(messages):
                if m.role == "user":
                    last_user = m
                    break
            if last_user:
                self.session_manager.append_message(
                    session_id,
                    SessionMessage(
                        type="user",
                        content=str(last_user.content) if last_user.content else "",
                        role="user",
                    ),
                )

        llm = self._get_llm(req)
        max_tool_rounds = 5

        for round_num in range(max_tool_rounds):
            # Check context compaction
            if self.context_compactor.should_compact(messages):
                messages, summary = self.context_compactor.compact(messages)
                # Add compaction summary
                if summary.summary_text:
                    messages.insert(
                        0,
                        Message(role="system", content=summary.summary_text),
                    )

            output = await llm.achat(
                messages,
                tools=tools,
                tool_choice="auto",
            )

            # Record API usage
            if output.usage:
                self.cost_tracker.record_usage(
                    model_name=llm.config.model_name,
                    input_tokens=output.usage.get("input_tokens", 0),
                    output_tokens=output.usage.get("output_tokens", 0),
                )

            if output.finish_reason == "tool_calls" and output.tool_calls:
                # Save assistant message with tool_calls
                self.session_manager.append_message(
                    session_id,
                    SessionMessage(
                        type="assistant",
                        content=output.text or "",
                        role="assistant",
                        tool_calls=[
                            {"id": tc.id, "type": tc.type, "function": tc.function}
                            for tc in output.tool_calls
                        ],
                    ),
                )

                messages.append(
                    Message(
                        role="assistant",
                        content=output.text,
                        tool_calls=output.tool_calls,
                    )
                )
                tool_results, used_csv_analysis = await self._execute_tool_calls(
                    output.tool_calls, session_id
                )
                messages.extend(tool_results)
                if used_csv_analysis:
                    messages.append(
                        Message(role="system", content=CSV_CHART_PROMPT),
                    )
                continue

            # Final answer
            # Save to session
            self.session_manager.append_message(
                session_id,
                SessionMessage(
                    type="assistant",
                    content=output.text or "",
                    role="assistant",
                ),
            )

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

        # Fallback
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

    async def chat_stream(
        self,
        req: ChatRequest,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream chat with tool call events."""
        if not session_id:
            session = await self.start_session()
            session_id = session.id

        messages = self._build_messages(req)

        # Add memory context
        memory_context = self.memory_manager.get_memory_context()
        if memory_context:
            messages.insert(0, Message(role="system", content=memory_context))

        model_type = req.model_config_field.model_type if req.model_config_field else "openai"
        tools = None
        if model_type not in ("anthropic", "kimi"):
            tools = self._build_tools()

        if tools and (not messages or messages[0].role != "system"):
            system_prompt = self.prompt_builder.build_single_string()
            messages.insert(
                0,
                Message(role="system", content=system_prompt),
            )

        # Inject user context (CLAUDE.md + date)
        user_context = self.prompt_builder.get_user_context()
        if user_context:
            messages.insert(
                0,
                Message(role="user", content=f"<system-reminder>\n{user_context}\n</system-reminder>"),
            )

        # Inject system context (git status)
        system_context = self.prompt_builder.get_system_context()
        if system_context and messages and messages[0].role == "system":
            messages[0] = Message(
                role="system",
                content=messages[0].content + "\n\n" + system_context,
            )

        llm = self._get_llm(req)

        if tools:
            max_tool_rounds = 5
            for _ in range(max_tool_rounds):
                # Context compaction check
                if self.context_compactor.should_compact(messages):
                    messages, summary = self.context_compactor.compact(messages)

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

                    # Emit tool_call_start events
                    for tc in output.tool_calls:
                        if tc.type != "function":
                            continue
                        yield f"data: {json.dumps({'type': 'tool_call_start', 'tool_name': tc.function.get('name', ''), 'arguments': tc.function.get('arguments', '{}')})}\n\n"

                    tool_results, used_csv_analysis = await self._execute_tool_calls(
                        output.tool_calls, session_id
                    )

                    # Emit tool_call_result events
                    for tr in tool_results:
                        yield f"data: {json.dumps({'type': 'tool_call_result', 'tool_name': tr.name or '', 'content': str(tr.content) if tr.content else ''})}\n\n"

                    messages.extend(tool_results)
                    if used_csv_analysis:
                        messages.append(
                            Message(role="system", content=CSV_CHART_PROMPT),
                        )
                    continue

                # Stream the final text response as deltas
                resp_id = f"chatbi-{int(time.time() * 1000)}"
                created = int(time.time())
                model_name = llm.config.model_name
                full_text = output.text or ""

                yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
                for i in range(0, len(full_text), 10):
                    yield f"data: {json.dumps({'type': 'text_delta', 'content': full_text[i:i+10]})}\n\n"
                yield f"data: {json.dumps({'type': 'text_end', 'id': resp_id, 'created': created, 'model': model_name, 'finish_reason': output.finish_reason, 'usage': output.usage})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Max rounds reached
            yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'content': 'Reached maximum tool calling rounds.'})}\n\n"
            yield f"data: {json.dumps({'type': 'text_end', 'finish_reason': 'stop'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        created = int(time.time())
        model_name = llm.config.model_name

        yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
        async for chunk in llm.achat_stream(messages):
            yield f"data: {json.dumps({'type': 'text_delta', 'content': chunk.text})}\n\n"
            if chunk.finish_reason:
                yield f"data: {json.dumps({'type': 'text_end', 'finish_reason': chunk.finish_reason})}\n\n"
        yield "data: [DONE]\n\n"

    def get_status(self) -> dict:
        """Get current application status snapshot.

        Returns a JSON-serializable status dict with model info,
        token usage, cost, tool stats, git info, and memory stats.
        """
        from chatbi_core.status.models import StatusData, WorkspaceInfo, GitInfo

        git_info = GitInfo()
        try:
            import subprocess
            from pathlib import Path
            project_path = Path.cwd()
            if (project_path / ".git").exists():
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=5,
                )
                git_info.branch = branch_result.stdout.strip()
                status_result = subprocess.run(
                    ["git", "status", "--short"],
                    capture_output=True, text=True, timeout=5,
                )
                git_info.has_uncommitted_changes = bool(status_result.stdout.strip())
        except Exception:
            pass

        workspace = WorkspaceInfo(
            current_dir=str(Path.cwd()),
            project_dir=str(Path.cwd()),
        )

        model_display = getattr(
            getattr(self, "registry", None), "default_model", "unknown"
        )

        status = StatusData(
            session_id=getattr(self, "_current_session_id", ""),
            model=ModelInfo(
                id=str(model_display),
                display_name=str(model_display),
                provider="openai",
            ),
            context_window=self.cost_tracker.get_context_window(),
            current_usage=self.cost_tracker.get_current_usage(),
            cost=self.cost_tracker.get_cost_stats(),
            workspace=workspace,
            tools=self.cost_tracker.get_tool_stats(
                active_tool_count=len(self.tool_registry.get_active_tools())
            ),
            git=git_info,
            memory=self.cost_tracker.get_memory_stats(self.memory_manager),
            permission_mode=self.permission_manager.mode
            if hasattr(self.permission_manager, "mode")
            else PermissionMode.DEFAULT,
        )
        return status.to_dict()

    def resume_session(self, session_id: str) -> Optional[Session]:
        """Resume a previous session."""
        return self.session_manager.resume_session(session_id)

    def fork_session(self, session_id: str) -> Optional[Session]:
        """Fork a session to try different approach."""
        return self.session_manager.fork_session(session_id)

    def list_sessions(self, project_path: Optional[str] = None) -> List[Dict]:
        """List available sessions."""
        return self.session_manager.list_sessions(project_path)

    def save_memory(
        self,
        type: MemoryType,
        name: str,
        description: str,
        content: str,
    ) -> str:
        """Save a memory entry."""
        return self.memory_manager.auto_save(type, name, description, content)

    def set_permission_mode(self, mode: PermissionMode) -> None:
        """Set permission mode."""
        self.permission_manager.set_mode(mode)

    def register_subagent(self, definition: SubagentDefinition) -> str:
        """Register a custom subagent."""
        return self.subagent_manager.save_definition(definition)


# Backward compatibility: alias original ChatService
ChatService = EnhancedChatService