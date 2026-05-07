"""Tool registry — ported from Claude-Code's tools.ts.

Provides:
- ToolRegistry class for runtime tool registration
- get_all_base_tools() — all built-in tools
- get_tools() — tools filtered by permission context
- get_merged_tools() — built-in + MCP tools
"""

from typing import Dict, List, Optional, Sequence

from aurora_core.tool.base import (
    Tool,
    ToolPermissionContext,
    assemble_tool_pool,
    filter_tools_by_deny_rules,
)


class ToolRegistry:
    """Runtime registry for tools.

    Mirrors the pattern in Claude-Code where tools are assembled
    from built-in definitions + MCP servers + dynamic skills.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._mcp_tools: Dict[str, Tool] = {}
        self._permission_context = ToolPermissionContext()

    # ── Registration ────────────────────────────────────────────

    def register(self, tool: Tool) -> None:
        """Register a built-in tool."""
        self._tools[tool.name] = tool

    def register_mcp(self, tool: Tool) -> None:
        """Register an MCP-provided tool."""
        self._mcp_tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)
        self._mcp_tools.pop(name, None)

    def register_all(self, tools: Sequence[Tool]) -> None:
        """Register multiple built-in tools at once."""
        for t in tools:
            self._tools[t.name] = t

    # ── Lookup ──────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name (checks built-in then MCP)."""
        return self._tools.get(name) or self._mcp_tools.get(name)

    def get_builtin(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_mcp(self, name: str) -> Optional[Tool]:
        return self._mcp_tools.get(name)

    def list_tools(self) -> List[Dict[str, object]]:
        """List all tool metadata for API responses."""
        return [t.to_dict() for t in self.get_active_tools()]

    # ── Assembly ────────────────────────────────────────────────

    def get_active_tools(self) -> List[Tool]:
        """Get filtered and assembled tool list for the current context."""
        builtin = list(self._tools.values())
        mcp = list(self._mcp_tools.values())
        return assemble_tool_pool(builtin, mcp, self._permission_context)

    def set_permission_context(self, ctx: ToolPermissionContext) -> None:
        self._permission_context = ctx

    # ── State ───────────────────────────────────────────────────

    def clear(self) -> None:
        self._tools.clear()
        self._mcp_tools.clear()


# ── Module-level helpers ──────────────────────────────────────────────


def get_all_base_tools() -> List[Tool]:
    """Return all available built-in tool instances.

    Mirrors getAllBaseTools() in tools.ts.
    Lazy-imports individual tools to avoid circular imports.
    """
    from aurora_core.tool.tools.bash import BashTool
    from aurora_core.tool.tools.read import ReadTool
    from aurora_core.tool.tools.write import WriteTool
    from aurora_core.tool.tools.edit import EditTool
    from aurora_core.tool.tools.glob import GlobTool
    from aurora_core.tool.tools.grep import GrepTool
    from aurora_core.tool.tools.web_fetch import WebFetchTool
    from aurora_core.tool.tools.web_search import WebSearchTool
    from aurora_core.tool.tools.agent import AgentTool
    from aurora_core.tool.tools.task import TaskOutputTool
    from aurora_core.tool.tools.ask_user_question import AskUserQuestionTool
    from aurora_core.tool.tools.skill import SkillTool
    from aurora_core.tool.tools.enter_plan_mode import EnterPlanModeTool
    from aurora_core.tool.tools.exit_plan_mode import ExitPlanModeTool
    from aurora_core.tool.tools.send_message import SendMessageTool
    from aurora_core.tool.tools.notebook_edit import NotebookEditTool
    from aurora_core.tool.tools.lsp import LSPTool
    from aurora_core.tool.tools.todo_write import TodoWriteTool
    from aurora_core.tool.tools.task_create import TaskCreateTool
    from aurora_core.tool.tools.task_get import TaskGetTool
    from aurora_core.tool.tools.task_update import TaskUpdateTool
    from aurora_core.tool.tools.task_list import TaskListTool
    from aurora_core.tool.tools.task_stop import TaskStopTool

    return [
        BashTool,
        ReadTool,
        WriteTool,
        EditTool,
        GlobTool,
        GrepTool,
        WebFetchTool,
        WebSearchTool,
        AgentTool,
        TaskOutputTool,
        AskUserQuestionTool,
        SkillTool,
        EnterPlanModeTool,
        ExitPlanModeTool,
        SendMessageTool,
        NotebookEditTool,
        LSPTool,
        TodoWriteTool,
        TaskCreateTool,
        TaskGetTool,
        TaskUpdateTool,
        TaskListTool,
        TaskStopTool,
    ]


def get_tools(permission_context: ToolPermissionContext) -> List[Tool]:
    """Get built-in tools filtered by permission context.

    Mirrors getTools() in tools.ts.
    """
    all_tools = get_all_base_tools()
    enabled = [t for t in all_tools if t.is_enabled()]
    return filter_tools_by_deny_rules(enabled, permission_context)


def get_merged_tools(
    permission_context: ToolPermissionContext,
    mcp_tools: Sequence[Tool],
) -> List[Tool]:
    """Get combined built-in + MCP tools, deduplicated and filtered.

    Mirrors getMergedTools() in tools.ts.
    """
    builtin = get_tools(permission_context)
    return list(builtin) + list(mcp_tools)
