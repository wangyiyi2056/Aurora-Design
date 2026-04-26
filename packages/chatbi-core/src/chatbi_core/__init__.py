"""ChatBI core framework - Claude Code architecture upgrade."""

__version__ = "0.4.0"

# Session Management
from chatbi_core.session import SessionManager, Session, SessionMessage

# Memory Management
from chatbi_core.memory import MemoryManager, MemoryEntry, MemoryType

# Hooks System
from chatbi_core.hooks import HookManager, Hook, HookType, HookMatcher

# Context Management
from chatbi_core.context import (
    ContextCompactor,
    ToolSearchManager,
    ContextMonitor,
    ContextSnapshot,
    CompactionConfig,
    ContextSummary,
    ToolDefinition,
    ToolSearchResult,
)

# Subagents System
from chatbi_core.subagents import SubagentManager, SubagentDefinition

# MCP Integration
from chatbi_core.mcp import MCPClient, MCPConfig, MCPServerConfig

# Skills System
from chatbi_core.skills import SkillsLoader, SkillFile

# Query Engine (ported from Claude Code)
from chatbi_core.query import (
    QueryEngine,
    QueryConfig,
    TaskComplexity,
)

# Status System (ported from Claude Code)
from chatbi_core.status import (
    StatusData,
    ModelInfo,
    ContextWindow,
    CurrentUsage,
    CostStats,
    WorkspaceInfo,
    ToolStats,
    GitInfo,
    MemoryStats,
    CostTracker,
    ModelUsage,
    MODEL_PRICING,
    DEFAULT_PRICING,
)

# Permissions System
from chatbi_core.permissions import PermissionManager, PermissionMode, PermissionConfig

# Agent Skill Base (existing)
from chatbi_core.agent.skill.base import BaseSkill, SkillRegistry

# Prompt System (ported from Claude Code)
from chatbi_core.prompt import (
    PromptSection,
    STATIC_SECTIONS,
    DYNAMIC_SECTIONS,
    get_intro_section,
    get_system_section,
    get_tool_usage_section,
    get_tone_style_section,
    get_output_efficiency_section,
    get_environment_section,
    get_session_section,
    PromptContext,
    ContextProvider,
    get_date_context,
    get_git_context,
    get_claude_md_context,
    get_memory_context,
    get_project_context,
    PromptBuilder,
    build_system_prompt,
    build_system_prompt_block,
    DYNAMIC_BOUNDARY,
)

# Tool System (ported from Claude Code)
from chatbi_core.tool import (
    Tool,
    ToolResult,
    ToolUseContext,
    ToolPermissionContext,
    ToolProgress,
    ToolCallProgress,
    build_tool,
    tool_matches_name,
    find_tool_by_name,
    filter_tools_by_deny_rules,
    assemble_tool_pool,
    ToolRegistry,
    get_all_base_tools,
    get_tools,
    get_merged_tools,
    run_tool_use,
    run_tools,
    StreamingToolExecutor,
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
)

__all__ = [
    # Session
    "SessionManager",
    "Session",
    "SessionMessage",
    # Memory
    "MemoryManager",
    "MemoryEntry",
    "MemoryType",
    # Hooks
    "HookManager",
    "Hook",
    "HookType",
    "HookMatcher",
    # Context
    "ContextCompactor",
    "ToolSearchManager",
    "ContextMonitor",
    "ContextSnapshot",
    "CompactionConfig",
    "ContextSummary",
    "ToolDefinition",
    "ToolSearchResult",
    # Subagents
    "SubagentManager",
    "SubagentDefinition",
    # MCP
    "MCPClient",
    "MCPConfig",
    "MCPServerConfig",
    # Skills
    "SkillsLoader",
    "SkillFile",
    # Query
    "QueryEngine",
    "QueryConfig",
    "TaskComplexity",
    # Status
    "StatusData",
    "ModelInfo",
    "ContextWindow",
    "CurrentUsage",
    "CostStats",
    "WorkspaceInfo",
    "ToolStats",
    "GitInfo",
    "MemoryStats",
    "CostTracker",
    "ModelUsage",
    "MODEL_PRICING",
    "DEFAULT_PRICING",
    # Permissions
    "PermissionManager",
    "PermissionMode",
    "PermissionConfig",
    # Agent
    "BaseSkill",
    "SkillRegistry",
    # Prompt
    "PromptSection",
    "STATIC_SECTIONS",
    "DYNAMIC_SECTIONS",
    "get_intro_section",
    "get_system_section",
    "get_tool_usage_section",
    "get_tone_style_section",
    "get_output_efficiency_section",
    "get_environment_section",
    "get_session_section",
    "PromptContext",
    "ContextProvider",
    "get_date_context",
    "get_git_context",
    "get_claude_md_context",
    "get_memory_context",
    "get_project_context",
    "PromptBuilder",
    "build_system_prompt",
    "build_system_prompt_block",
    "DYNAMIC_BOUNDARY",
    # Tool
    "Tool",
    "ToolResult",
    "ToolUseContext",
    "ToolPermissionContext",
    "ToolProgress",
    "ToolCallProgress",
    "build_tool",
    "tool_matches_name",
    "find_tool_by_name",
    "filter_tools_by_deny_rules",
    "assemble_tool_pool",
    "ToolRegistry",
    "get_all_base_tools",
    "get_tools",
    "get_merged_tools",
    "run_tool_use",
    "run_tools",
    "StreamingToolExecutor",
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "WebFetchTool",
    "WebSearchTool",
    "AgentTool",
    "TaskOutputTool",
    "AskUserQuestionTool",
    "SkillTool",
    "EnterPlanModeTool",
    "ExitPlanModeTool",
    "SendMessageTool",
    "NotebookEditTool",
    "LSPTool",
    "TodoWriteTool",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskUpdateTool",
    "TaskListTool",
    "TaskStopTool",
]
