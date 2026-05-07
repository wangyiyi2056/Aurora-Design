"""Enhanced Chat Service with Claude Code architecture."""

import json
import logging
import re
import time
from html import escape
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

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
from chatbi_core.model.base import BaseLLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ToolCall
from chatbi_core.schema.model import LLMConfig
from chatbi_core.mode import ChatMode
from chatbi_serve.excel.pipeline import ExcelAnalysisPipeline
from chatbi_serve.agent.sql_agent import SQLAgent
from chatbi_serve.datasource.service import DatasourceService
from chatbi_serve.knowledge.service import KnowledgeService
from chatbi_serve.chat.schema import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContentPart,
    FileUrlPart,
    ReactAgentRequest,
)

# Plan mode system (ported from Claude Code)
from chatbi_core.plan import PlanEnforcer

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
        skill_registry: Optional[SkillRegistry] = None,
        project_path: Optional[str] = None,
        mcp_client: Optional["MCPClient"] = None,
        mode: ChatMode = ChatMode.BI,
        session_base_path: Optional[str] = None,
        datasource_service: Optional[DatasourceService] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ):
        self.registry = model_registry
        self.skill_registry = skill_registry
        self.mcp_client = mcp_client
        self.datasource_service = datasource_service
        self.knowledge_service = knowledge_service

        # Initialize Claude Code architecture components
        self.session_manager = SessionManager(base_path=session_base_path)

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

        # Initialize PlanEnforcer (ported from Claude Code)
        self.plan_enforcer = PlanEnforcer()

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
            mode=mode,
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
            saved_llm = self._get_saved_llm_for_request(req)
            if saved_llm is not None and not self._has_plain_inline_api_key(req.model_config_field.api_key):
                return saved_llm

            model_type = req.model_config_field.model_type or "openai"
            cfg = LLMConfig(
                model_name=req.model_config_field.model_name,
                model_type=model_type,
                api_base=req.model_config_field.base_url,
                api_key=req.model_config_field.api_key,
            )
            # Kimi Coding API uses OpenAI format, force OpenAI adapter
            if "kimi.com/coding" in (req.model_config_field.base_url or ""):
                return OpenAILLM(cfg)
            if model_type == "anthropic":
                return AnthropicLLM(cfg)
            return OpenAILLM(cfg)
        return self.registry.get_llm(req.model)

    def _get_saved_llm_for_request(self, req: ChatRequest) -> BaseLLM | None:
        for name in (req.model, req.model_config_field.model_name if req.model_config_field else None):
            if not name:
                continue
            try:
                return self.registry.get_llm(name)
            except KeyError:
                continue
        return None

    @staticmethod
    def _has_plain_inline_api_key(api_key: str | None) -> bool:
        if not api_key:
            return False
        return "..." not in api_key

    def _effective_model_type(self, req: ChatRequest) -> str:
        saved_llm = self._get_saved_llm_for_request(req)
        if saved_llm is not None and (
            not req.model_config_field
            or not self._has_plain_inline_api_key(req.model_config_field.api_key)
        ):
            return saved_llm.config.model_type
        if req.model_config_field:
            if "kimi.com/coding" in (req.model_config_field.base_url or ""):
                return "openai"
            return req.model_config_field.model_type
        return "openai"

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        """Extract human-readable text from message content (str or list of ContentParts)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and part.get("text"):
                        texts.append(part["text"])
                elif hasattr(part, "text") and part.text:
                    texts.append(part.text)
            return " ".join(texts)
        return str(content) if content else ""

    def _read_tabular_file(self, file_path: Path) -> str:
        """Read Excel/CSV file and return readable text for the LLM."""
        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            import pandas as pd

            df = pd.read_csv(str(file_path), encoding="utf-8-sig", keep_default_na=True)
            if df.empty:
                return "[Empty CSV file]"

            profile = self._build_data_profile(df)
            headers = [str(h) for h in df.columns]
            rows = [
                [str(df.iloc[i, j]) for j in range(len(headers))]
                for i in range(len(df))
            ]
            table = self._format_table(headers, rows)
            return f"{profile}\n\n{table}"

        if suffix in (".xlsx", ".xls"):
            import pandas as pd

            df = pd.read_excel(str(file_path), engine="openpyxl", keep_default_na=True)
            if df.empty:
                return "[Empty Excel file]"

            profile = self._build_data_profile(df)
            headers = [str(h) for h in df.columns]
            rows = [
                [str(df.iloc[i, j]) for j in range(len(headers))]
                for i in range(len(df))
            ]
            table = self._format_table(headers, rows)
            return f"{profile}\n\n{table}"

        # Fallback: try to read as text
        return file_path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _is_tabular_file_name(file_name: str) -> bool:
        return Path(file_name).suffix.lower() in {".csv", ".xlsx", ".xls"}

    def _extract_latest_tabular_attachment(
        self, req: ChatRequest
    ) -> tuple[str, str] | None:
        """Return (file_path, file_name) for the latest user tabular file attachment."""
        for message in reversed(req.messages):
            if message.role != "user" or not isinstance(message.content, list):
                continue
            for part in message.content:
                if part.type != "file_url" or part.file_url is None:
                    continue
                file_name = part.file_url.file_name or Path(part.file_url.url).name
                if self._is_tabular_file_name(file_name):
                    return part.file_url.url, file_name
        return None

    def _extract_latest_user_question(self, req: ChatRequest) -> str:
        """Extract text question from the latest user message."""
        for message in reversed(req.messages):
            if message.role != "user":
                continue
            if isinstance(message.content, str):
                return message.content.strip()
            texts: list[str] = []
            for part in message.content:
                if part.type == "text" and part.text:
                    texts.append(part.text)
            return " ".join(texts).strip()
        return ""

    async def _run_excel_analysis(
        self,
        req: ChatRequest,
        emit_step: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ) -> str | None:
        """Run deterministic Excel/CSV analysis when the request carries a table file."""
        attachment = self._extract_latest_tabular_attachment(req)
        if not attachment:
            return None

        file_path, file_name = attachment
        if not Path(file_path).exists():
            return f"File not found: {file_path}"

        question = self._extract_latest_user_question(req)
        if not question:
            question = "请分析这份表格数据"

        llm = self._get_llm(req)
        pipeline = ExcelAnalysisPipeline(
            llm=llm,
            file_path=file_path,
            file_name=file_name,
            database=":memory:",
            table_name="data_analysis_table",
            language="zh",
            emit_step=emit_step,
        )
        try:
            return await pipeline.analyze(question)
        finally:
            pipeline.close()

    async def _run_datasource_analysis(self, req: ChatRequest) -> str | None:
        if not self.datasource_service:
            return None
        datasource_name = (req.ext_info or {}).get("database_name")
        if not datasource_name:
            return None
        question = self._extract_latest_user_question(req)
        if not question:
            return None
        agent = SQLAgent(self.registry, self.datasource_service, str(datasource_name))
        if not agent.is_sql_question(question):
            return None
        ok, result = await agent.run(question, str(datasource_name))
        if ok:
            return result
        return f"Datasource query failed: {result}"

    def _knowledge_names_from_ext_info(self, req: ChatRequest) -> list[str]:
        ext_info = req.ext_info or {}
        raw = (
            ext_info.get("knowledge_ids")
            or ext_info.get("knowledge_names")
            or ext_info.get("knowledge_base")
            or ext_info.get("knowledge_name")
        )
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw else []
        if isinstance(raw, list):
            return [str(item) for item in raw if item]
        return []

    async def _build_knowledge_context(self, req: ChatRequest) -> str:
        if not self.knowledge_service:
            return ""
        names = self._knowledge_names_from_ext_info(req)
        if not names:
            return ""
        question = self._extract_latest_user_question(req)
        if not question:
            return ""

        sections: list[str] = []
        top_k = int((req.ext_info or {}).get("knowledge_top_k") or 5)
        for name in names:
            try:
                result = await self.knowledge_service.query(name, question, top_k=top_k)
            except Exception as exc:
                sections.append(f"[{name}] retrieval failed: {exc}")
                continue
            docs = result.get("results", []) if isinstance(result, dict) else []
            if not docs:
                continue
            snippets = []
            for idx, doc in enumerate(docs[:top_k], start=1):
                content = doc.get("content", "") if isinstance(doc, dict) else str(doc)
                metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
                source = metadata.get("source") or metadata.get("file_name") or metadata.get("path") or ""
                prefix = f"{idx}. "
                if source:
                    prefix += f"[{source}] "
                snippets.append(prefix + str(content))
            if snippets:
                sections.append(f"Knowledge base: {name}\n" + "\n".join(snippets))
        if not sections:
            return ""
        return "Knowledge context:\n" + "\n\n".join(sections)

    @staticmethod
    def _sse_event(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _strip_vis_chart_blocks(text: str) -> str:
        return re.sub(r"```vis-chart\s*[\s\S]*?```", "", text or "").strip()

    @staticmethod
    def _extract_vis_chart_payloads(text: str) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for match in re.finditer(r"```vis-chart\s*([\s\S]*?)```", text or ""):
            try:
                payload = json.loads(match.group(1).strip())
                if isinstance(payload, dict):
                    payloads.append(payload)
            except json.JSONDecodeError:
                continue
        return payloads

    @classmethod
    def _build_report_html(cls, analysis_text: str, question: str) -> str:
        charts = cls._extract_vis_chart_payloads(analysis_text)
        summary = cls._strip_vis_chart_blocks(analysis_text) or "分析完成。"
        chart_sections: list[str] = []
        for idx, chart in enumerate(charts, start=1):
            data = chart.get("data") or []
            sql = chart.get("sql") or ""
            columns = list(data[0].keys()) if isinstance(data, list) and data else []
            rows = []
            for row in data[:100] if isinstance(data, list) else []:
                rows.append(
                    "<tr>"
                    + "".join(f"<td>{escape(str(row.get(col, '')))}</td>" for col in columns)
                    + "</tr>"
                )
            table = (
                "<table><thead><tr>"
                + "".join(f"<th>{escape(str(col))}</th>" for col in columns)
                + "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
                if columns
                else "<p class='muted'>暂无表格数据</p>"
            )
            chart_sections.append(
                f"""
                <section class="card">
                  <div class="card-title">结果 {idx} · {escape(str(chart.get('type', 'table')))}</div>
                  {table}
                  <details><summary>SQL</summary><pre>{escape(str(sql))}</pre></details>
                </section>
                """
            )
        if not chart_sections:
            chart_sections.append("<section class='card'><p class='muted'>没有生成可视化数据。</p></section>")
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Report</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f7f8fb; color: #1f2937; }}
    .shell {{ max-width: 1120px; margin: 0 auto; padding: 32px; }}
    .hero {{ background: #101828; color: white; padding: 28px; border-radius: 18px; }}
    .hero h1 {{ margin: 0 0 10px; font-size: 28px; }}
    .hero p {{ margin: 0; color: #d0d5dd; line-height: 1.7; }}
    .grid {{ display: grid; gap: 18px; margin-top: 20px; }}
    .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 16px; padding: 20px; box-shadow: 0 10px 30px rgba(15,23,42,.06); }}
    .card-title {{ font-weight: 700; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #edf0f3; padding: 10px 12px; text-align: left; }}
    th {{ color: #667085; background: #f9fafb; }}
    pre {{ white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 14px; border-radius: 10px; overflow: auto; }}
    details {{ margin-top: 16px; }}
    summary {{ cursor: pointer; color: #2563eb; font-weight: 600; }}
    .muted {{ color: #667085; }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>数据分析报告</h1>
      <p><strong>问题：</strong>{escape(question)}</p>
    </section>
    <section class="card">
      <div class="card-title">分析摘要</div>
      <p>{escape(summary).replace(chr(10), "<br />")}</p>
    </section>
    <div class="grid">{''.join(chart_sections)}</div>
  </main>
</body>
</html>"""

    def _react_agent_chat_request(self, req: ReactAgentRequest) -> ChatRequest:
        file_path = (req.ext_info or {}).get("file_path", "")
        file_name = (req.ext_info or {}).get("file_name") or Path(str(file_path)).name
        content: list[ContentPart] = []
        if file_path:
            content.append(
                ContentPart(
                    type="file_url",
                    file_url=FileUrlPart(url=str(file_path), file_name=str(file_name)),
                )
            )
        content.append(ContentPart(type="text", text=req.user_input))
        return ChatRequest(
            model=req.model_name,
            messages=[ChatMessage(role="user", content=content)],
            stream=True,
            model_config=req.model_config_field,
            ext_info=req.ext_info,
            session_id=req.conv_uid,
        )

    async def react_agent_stream(self, req: ReactAgentRequest) -> AsyncIterator[str]:
        """DB-GPT compatible ReAct stream for tabular report analysis."""
        chat_req = self._react_agent_chat_request(req)
        question = req.user_input.strip() or "Analyze the uploaded file."
        file_path = str((req.ext_info or {}).get("file_path", ""))
        steps = [
            ("step-read-file", "读取文件", "load_file", {"file_path": file_path}),
            ("step-learn-structure", "学习数据结构", "excel_learning", {"file_path": file_path}),
            ("step-generate-sql", "生成 SQL", "generate_sql", {"question": question}),
            ("step-execute-sql", "执行 SQL", "execute_sql", {"engine": "duckdb"}),
            ("step-render-report", "渲染 Report.html", "html_interpreter", {"title": "Report"}),
        ]
        active_started: set[str] = set()

        def start_step(index: int) -> str:
            step_id, title, _action, _input = steps[index]
            active_started.add(step_id)
            return self._sse_event(
                {
                    "type": "step.start",
                    "step": index + 1,
                    "id": step_id,
                    "title": title,
                    "detail": title,
                    "phase": "analysis",
                }
            )

        for idx in range(2):
            step_id, title, action, action_input = steps[idx]
            yield start_step(idx)
            yield self._sse_event(
                {
                    "type": "step.meta",
                    "id": step_id,
                    "title": title,
                    "thought": f"准备{title}",
                    "action": action,
                    "action_input": action_input,
                }
            )

        analysis_text = await self._run_excel_analysis(chat_req)
        if analysis_text is None:
            analysis_text = "未检测到可分析的 Excel/CSV 文件。"

        for idx in range(2):
            step_id = steps[idx][0]
            yield self._sse_event({"type": "step.done", "id": step_id, "status": "done"})

        for idx in range(2, 4):
            step_id, title, action, action_input = steps[idx]
            yield start_step(idx)
            yield self._sse_event(
                {
                    "type": "step.meta",
                    "id": step_id,
                    "title": title,
                    "thought": f"根据用户问题执行{title}",
                    "action": action,
                    "action_input": action_input,
                }
            )
            if idx == 2:
                for payload in self._extract_vis_chart_payloads(analysis_text):
                    if payload.get("sql"):
                        yield self._sse_event(
                            {
                                "type": "step.chunk",
                                "id": step_id,
                                "output_type": "code",
                                "content": payload["sql"],
                            }
                        )
            else:
                for payload in self._extract_vis_chart_payloads(analysis_text):
                    yield self._sse_event(
                        {
                            "type": "step.chunk",
                            "id": step_id,
                            "output_type": "json",
                            "content": payload,
                        }
                    )
            yield self._sse_event({"type": "step.done", "id": step_id, "status": "done"})

        report_html = self._build_report_html(analysis_text, question)
        render_step = steps[4]
        yield start_step(4)
        yield self._sse_event(
            {
                "type": "step.meta",
                "id": render_step[0],
                "title": render_step[1],
                "thought": "将分析结果整理为右侧可预览的 HTML 报告",
                "action": render_step[2],
                "action_input": render_step[3],
            }
        )
        yield self._sse_event(
            {
                "type": "step.chunk",
                "id": render_step[0],
                "output_type": "html",
                "content": {"html": report_html, "title": "Report"},
            }
        )
        yield self._sse_event({"type": "step.done", "id": render_step[0], "status": "done"})

        summary = self._strip_vis_chart_blocks(analysis_text) or "分析完成，已生成 Report.html。"
        yield self._sse_event({"type": "final", "content": summary})
        yield self._sse_event({"type": "done"})

    @staticmethod
    def _format_table(headers: list, rows: list) -> str:
        """Format tabular data as a readable pipe-separated table."""
        lines = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---" for _ in headers]) + "|")
        for row in rows[:200]:  # cap at 200 rows to avoid token blowout
            cells = [str(c).replace("\n", " ").replace("|", "\\|") for c in row]
            lines.append("| " + " | ".join(cells) + " |")
        if len(rows) > 200:
            lines.append(f"\n... ({len(rows) - 200} more rows omitted)")
        return "\n".join(lines)

    @staticmethod
    def _build_data_profile(df: "pd.DataFrame") -> str:
        """Lightweight data profiling for LLM context."""
        import pandas as pd

        lines: list[str] = []
        total_rows = len(df)
        total_cols = len(df.columns)
        lines.append("## Data Profile")
        lines.append(f"- Rows: {total_rows}, Columns: {total_cols}")

        col_infos: list[str] = []
        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            dtype = str(series.dtype)

            if pd.api.types.is_numeric_dtype(series):
                col_type = "numeric"
                stats = (
                    f"nulls={null_count}"
                    if null_count == total_rows
                    else f"min={series.min():.4g}, max={series.max():.4g}, "
                    f"mean={series.mean():.4g}, nulls={null_count}"
                )
            elif pd.api.types.is_datetime64_any_dtype(series):
                col_type = "datetime"
                stats = f"range=[{series.min()} ~ {series.max()}], nulls={null_count}"
            else:
                col_type = "categorical"
                unique = series.nunique()
                top_vals = (
                    series.value_counts().head(3).index.tolist()
                    if unique > 0
                    else []
                )
                stats = f"unique={unique}, top={top_vals}, nulls={null_count}"

            col_infos.append(f"  - `{col}` ({col_type}, {dtype}): {stats}")

        completeness = (
            f"{(1 - df.isna().any(axis=1).sum() / max(total_rows, 1)) * 100:.1f}%"
        )
        lines.append(f"- Complete rows: {completeness}")
        lines.append("- Columns:")
        lines.extend(col_infos)
        return "\n".join(lines)

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
                    try:
                        text = self._read_tabular_file(file_path)
                    except Exception:
                        text = file_path.read_text(
                            encoding="utf-8", errors="replace"
                        )
                else:
                    text = f"[File not found: {part.file_url.url}]"
                resolved.append(
                    {
                        "type": "text",
                        "text": (
                            f"[Attached file: {part.file_url.file_name}]\n{text}\n\n"
                            "IMPORTANT: You MUST analyze this file and generate a complete HTML "
                            "analysis report using a ```web code block. Include a KPI summary at "
                            "the top and at least one ECharts chart. The ```web block must contain "
                            "a full, self-contained HTML page."
                        ),
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

    def _selected_tool_names(self, req: ChatRequest) -> set[str]:
        names: set[str] = set()
        if req.select_param:
            names.add(req.select_param)
        ext_info = req.ext_info or {}
        raw = ext_info.get("skill_names") or ext_info.get("skill_name")
        if isinstance(raw, str) and raw:
            names.add(raw)
        elif isinstance(raw, list):
            names.update(str(item) for item in raw if item)
        return names

    def _build_tools(self, req: ChatRequest | None = None) -> List[Dict[str, Any]] | None:
        """Build tools for LLM using the new tool registry."""
        # Get active tools from the registry
        tools = self.tool_registry.get_active_tools()
        selected_names = self._selected_tool_names(req) if req is not None else set()
        if selected_names:
            tools = [tool for tool in tools if tool.name in selected_names]
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
    ) -> List[Message]:
        """Execute tool calls using the new Tool system."""
        if not self.tool_registry:
            return []

        tool_messages: List[Message] = []

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

        # Plan mode enforcement: block writes/destructive tools
        if self.plan_enforcer.is_plan_mode():
            for block in tool_blocks:
                tool_name = block.get("name", "")
                if not self.plan_enforcer.can_use_tool(tool_name):
                    msg = self.plan_enforcer.get_blocked_message(tool_name)
                    tool_messages.append(Message(
                        role="tool",
                        content=msg,
                        tool_call_id=block.get("id", ""),
                        name=tool_name,
                    ))
                    return tool_messages

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

        return tool_messages

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

        excel_result = await self._run_excel_analysis(req)
        if excel_result is not None:
            question = self._extract_latest_user_question(req)
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="user", content=question, role="user"),
            )
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="assistant", content=excel_result, role="assistant"),
            )
            return ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=int(time.time()),
                model=req.model or "excel-analysis",
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content=excel_result),
                        finish_reason="stop",
                    )
                ],
            )

        datasource_result = await self._run_datasource_analysis(req)
        if datasource_result is not None:
            question = self._extract_latest_user_question(req)
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="user", content=question, role="user"),
            )
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="assistant", content=datasource_result, role="assistant"),
            )
            return ChatResponse(
                id=f"chatbi-{int(time.time() * 1000)}",
                created=int(time.time()),
                model=req.model or "datasource-analysis",
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content=datasource_result),
                        finish_reason="stop",
                    )
                ],
            )

        messages = self._build_messages(req)

        knowledge_context = await self._build_knowledge_context(req)
        if knowledge_context:
            messages.insert(0, Message(role="system", content=knowledge_context))

        # Add memory context as system message
        memory_context = self.memory_manager.get_memory_context()
        if memory_context:
            messages.insert(
                0,
                Message(role="system", content=memory_context),
            )

        # Build system prompt using PromptBuilder (Claude Code architecture)
        model_type = self._effective_model_type(req)
        tools = None
        if model_type not in ("anthropic",):
            tools = self._build_tools(req)
        # Always inject system prompt (HTML report, chart vis, etc.) — independent of tools
        if not messages or messages[0].role != "system":
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
                        content=self._extract_text_content(last_user.content),
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

            try:
                output = await llm.achat(
                    messages,
                    tools=tools,
                    tool_choice="auto",
                )
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "AuthenticationError" in error_msg or "Incorrect API key" in error_msg:
                    return ChatResponse(
                        id=f"chatbi-{int(time.time() * 1000)}",
                        created=int(time.time()),
                        model=llm.config.model_name,
                        choices=[
                            ChatChoice(
                                message=ChatMessage(
                                    role="assistant",
                                    content="API Key 无效或已过期，请联系管理员更新。请检查配置中的 api_key 或环境变量 OPENAI_API_KEY。",
                                ),
                                finish_reason="error",
                            )
                        ],
                    )
                raise

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
                tool_results = await self._execute_tool_calls(
                    output.tool_calls, session_id
                )
                messages.extend(tool_results)
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

        if self._extract_latest_tabular_attachment(req):
            pipeline_events: list[dict[str, Any]] = []

            def emit_step(step_id: str, status: str, detail: Optional[str] = None) -> None:
                event: dict[str, Any] = {
                    "type": "pipeline_step",
                    "step_id": step_id,
                    "step_name": step_id,
                    "status": status,
                }
                if detail:
                    event["detail"] = detail[:200]
                pipeline_events.append(event)

            try:
                excel_result = await self._run_excel_analysis(req, emit_step=emit_step)
            except Exception as e:
                excel_result = f"Excel analysis failed: {e}"

            question = self._extract_latest_user_question(req)
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="user", content=question, role="user"),
            )
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="assistant", content=excel_result or "", role="assistant"),
            )

            for event in pipeline_events:
                yield f"data: {json.dumps(event)}\n\n"

            resp_id = f"chatbi-{int(time.time() * 1000)}"
            yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
            if excel_result:
                yield f"data: {json.dumps({'type': 'text_delta', 'content': excel_result})}\n\n"
            yield f"data: {json.dumps({'type': 'text_end', 'id': resp_id, 'created': int(time.time()), 'model': req.model or 'excel-analysis', 'finish_reason': 'stop', 'usage': None})}\n\n"
            yield "data: [DONE]\n\n"
            return

        datasource_result = await self._run_datasource_analysis(req)
        if datasource_result is not None:
            question = self._extract_latest_user_question(req)
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="user", content=question, role="user"),
            )
            self.session_manager.append_message(
                session_id,
                SessionMessage(type="assistant", content=datasource_result, role="assistant"),
            )
            resp_id = f"chatbi-{int(time.time() * 1000)}"
            yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'content': datasource_result})}\n\n"
            yield f"data: {json.dumps({'type': 'text_end', 'id': resp_id, 'created': int(time.time()), 'model': req.model or 'datasource-analysis', 'finish_reason': 'stop', 'usage': None})}\n\n"
            yield "data: [DONE]\n\n"
            return

        messages = self._build_messages(req)

        knowledge_context = await self._build_knowledge_context(req)
        if knowledge_context:
            messages.insert(0, Message(role="system", content=knowledge_context))

        # Add memory context
        memory_context = self.memory_manager.get_memory_context()
        if memory_context:
            messages.insert(0, Message(role="system", content=memory_context))

        model_type = self._effective_model_type(req)
        tools = None
        if model_type not in ("anthropic",):
            tools = self._build_tools(req)
        # Always inject system prompt (HTML report, chart vis, etc.) — independent of tools
        if not messages or messages[0].role != "system":
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

        # Save user message to session (same as chat() method)
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
                        content=self._extract_text_content(last_user.content),
                        role="user",
                    ),
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
                    # Save assistant message with tool_calls to session
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

                    # Emit tool_call_start events
                    for tc in output.tool_calls:
                        if tc.type != "function":
                            continue
                        yield f"data: {json.dumps({'type': 'tool_call_start', 'tool_name': tc.function.get('name', ''), 'arguments': tc.function.get('arguments', '{}')})}\n\n"

                    # For excel_analyze skill, set up emit_step callback to collect pipeline events
                    excel_skill = None
                    pipeline_events: list[dict] = []
                    if self.skill_registry:
                        for tc in output.tool_calls:
                            tool_name = tc.function.get("name", "")
                            if tool_name == "excel_analyze":
                                excel_skill = self.skill_registry.get("excel_analyze")
                                logger.info(f"[DEBUG] Got excel_skill: {excel_skill}, has set_emit_step: {hasattr(excel_skill, 'set_emit_step')}")
                                if excel_skill and hasattr(excel_skill, "set_emit_step"):
                                    def emit_step(step_id: str, status: str, detail: Optional[str] = None):
                                        logger.info(f"[DEBUG] emit_step called: {step_id} -> {status}")
                                        event_data = {
                                            "type": "pipeline_step",
                                            "step_id": step_id,
                                            "step_name": step_id,
                                            "status": status,
                                        }
                                        if detail:
                                            event_data["detail"] = detail[:100]
                                        pipeline_events.append(event_data)
                                    excel_skill.set_emit_step(emit_step)
                                    logger.info(f"[DEBUG] emit_step callback set on excel_skill")

                    tool_results = await self._execute_tool_calls(
                        output.tool_calls, session_id
                    )

                    # Emit collected pipeline_step events from excel_analyze
                    logger.info(f"[DEBUG] Pipeline events collected: {len(pipeline_events)}")
                    for event in pipeline_events:
                        yield f"data: {json.dumps(event)}\n\n"

                    # Emit tool_call_result events
                    for tr in tool_results:
                        yield f"data: {json.dumps({'type': 'tool_call_result', 'tool_name': tr.name or '', 'content': str(tr.content) if tr.content else ''})}\n\n"

                    messages.extend(tool_results)
                    continue

                # Stream the final text response as deltas
                resp_id = f"chatbi-{int(time.time() * 1000)}"
                created = int(time.time())
                model_name = llm.config.model_name
                full_text = output.text or ""

                # Save final answer to session
                self.session_manager.append_message(
                    session_id,
                    SessionMessage(
                        type="assistant",
                        content=full_text,
                        role="assistant",
                    ),
                )

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

        is_reasoning_started = False
        is_reasoning_ended = False
        is_text_started = False

        async for chunk in llm.achat_stream(messages):
            # Handle reasoning content (thinking) separately
            if chunk.is_reasoning:
                if not is_reasoning_started:
                    yield f"data: {json.dumps({'type': 'reasoning_start'})}\n\n"
                    is_reasoning_started = True
                # Don't send reasoning content, just indicate thinking is ongoing
                continue
            else:
                # Actual content starts - end reasoning phase if it was started
                if is_reasoning_started and not is_reasoning_ended:
                    yield f"data: {json.dumps({'type': 'reasoning_end'})}\n\n"
                    is_reasoning_ended = True

                # Send text_start before first content chunk
                if not is_text_started:
                    yield f"data: {json.dumps({'type': 'text_start'})}\n\n"
                    is_text_started = True

                if chunk.text:
                    yield f"data: {json.dumps({'type': 'text_delta', 'content': chunk.text})}\n\n"
                if chunk.finish_reason:
                    yield f"data: {json.dumps({'type': 'text_end', 'finish_reason': chunk.finish_reason})}\n\n"

        # If only reasoning happened without content, still send proper events
        if is_reasoning_started and not is_reasoning_ended:
            yield f"data: {json.dumps({'type': 'reasoning_end'})}\n\n"

        yield "data: [DONE]\n\n"

    def get_status(self) -> dict:
        """Get current application status snapshot.

        Returns a JSON-serializable status dict with model info,
        token usage, cost, tool stats, git info, and memory stats.
        """
        from chatbi_core.status.models import ModelInfo, StatusData, WorkspaceInfo, GitInfo

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

    def start_new_session(self, project_path: str = "") -> Session:
        """Create and return a new empty session."""
        return self.session_manager.create_session(project_path=project_path)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        return self.session_manager.delete_session(session_id)

    def set_session_title(self, session_id: str, title: str) -> bool:
        """Set a custom title for a session."""
        return self.session_manager.set_title(session_id, title)

    def load_session_full(self, session_id: str) -> Optional[Session]:
        """Load a full session with messages."""
        return self.session_manager.load_session(session_id)

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
