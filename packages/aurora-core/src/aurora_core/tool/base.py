"""Core tool types ported from Claude-Code's Tool.ts.

Mirrors the TypeScript Tool interface with all metadata fields,
ToolUseContext, ToolResult, build_tool(), and utility functions.
"""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

# ── Schema types ──────────────────────────────────────────────────────

ToolInputJSONSchema = Dict[str, Any]
"""JSON Schema for tool inputs (OpenAI function-calling style)."""

ToolInput = TypeVar("ToolInput", bound=Dict[str, Any])
ToolOutput = TypeVar("ToolOutput")

# ── Progress types ────────────────────────────────────────────────────


@dataclass
class BashProgress:
    """Progress data for Bash tool execution."""
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    exit_code: Optional[int] = None


@dataclass
class ReadProgress:
    """Progress data for Read tool execution."""
    file_path: str = ""
    bytes_read: int = 0
    total_bytes: Optional[int] = None


@dataclass
class WriteProgress:
    """Progress data for Write tool execution."""
    file_path: str = ""
    bytes_written: int = 0


@dataclass
class EditProgress:
    """Progress data for Edit tool execution."""
    file_path: str = ""
    diff: str = ""


@dataclass
class GlobProgress:
    """Progress data for Glob tool execution."""
    pattern: str = ""
    matches: int = 0


@dataclass
class GrepProgress:
    """Progress data for Grep tool execution."""
    pattern: str = ""
    matches: int = 0


@dataclass
class WebFetchProgress:
    """Progress data for WebFetch tool execution."""
    url: str = ""
    bytes_fetched: int = 0


@dataclass
class WebSearchProgress:
    """Progress data for WebSearch tool execution."""
    query: str = ""
    results: int = 0


@dataclass
class AgentProgress:
    """Progress data for Agent tool execution."""
    task: str = ""
    subagent_name: str = ""
    status: str = "running"  # running | completed | error


@dataclass
class TaskProgress:
    """Progress data for Task tool execution."""
    task_id: str = ""
    status: str = ""


ToolProgressData = Union[
    BashProgress,
    ReadProgress,
    WriteProgress,
    EditProgress,
    GlobProgress,
    GrepProgress,
    WebFetchProgress,
    WebSearchProgress,
    AgentProgress,
    TaskProgress,
]

Progress = ToolProgressData  # Extended with HookProgress later if needed


@dataclass
class ToolProgress:
    """A progress update during tool execution."""
    tool_use_id: str
    data: ToolProgressData


ToolCallProgress = Callable[[ToolProgress], None]
"""Callback type for reporting progress during tool execution."""

# ── Permission types ──────────────────────────────────────────────────


@dataclass
class PermissionResult:
    """Result of a permission check."""
    behavior: str  # 'allow' | 'deny' | 'ask'
    updated_input: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of input validation."""
    success: bool
    message: Optional[str] = None
    error_code: Optional[int] = None

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(success=True)

    @classmethod
    def fail(cls, message: str, error_code: int = 0) -> ValidationResult:
        return cls(success=False, message=message, error_code=error_code)


# ── ToolPermissionContext ─────────────────────────────────────────────


@dataclass
class ToolPermissionContext:
    """Permission context for tool execution."""
    mode: str = "default"  # 'default' | 'accept' | 'bypass'
    always_allow_rules: Dict[str, List[str]] = field(default_factory=dict)
    always_deny_rules: Dict[str, List[str]] = field(default_factory=dict)
    always_ask_rules: Dict[str, List[str]] = field(default_factory=dict)
    additional_working_directories: Dict[str, str] = field(default_factory=dict)

    @property
    def is_accept_mode(self) -> bool:
        return self.mode == "accept"

    @property
    def is_bypass_mode(self) -> bool:
        return self.mode == "bypass"


# ── ToolUseContext ────────────────────────────────────────────────────


@dataclass
class ToolUseContext:
    """Context passed to every tool call (mirrors Claude-Code's ToolUseContext).

    Provides access to:
    - The abort controller for cancellation
    - Application state getter/setter
    - Tool options and configuration
    - Progress reporting
    - Message management
    """
    options: Dict[str, Any] = field(default_factory=dict)
    abort_controller: Any = None  # Replace with proper AbortController
    messages: List[Any] = field(default_factory=list)
    tool_use_id: Optional[str] = None
    # Permission & state hooks
    permission_context: ToolPermissionContext = field(
        default_factory=ToolPermissionContext
    )

    # Simplified: in production this carries CanUseToolFn, readFileState,
    # agent definitions, theme, etc.

    def get_option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


# ── ToolResult ────────────────────────────────────────────────────────


ToolResultNewMessage = Dict[str, Any]


@dataclass
class ToolResult(Generic[ToolOutput]):
    """Result of a single tool execution (mirrors Claude-Code's ToolResult)."""
    data: ToolOutput
    new_messages: Optional[List[ToolResultNewMessage]] = None
    context_modifier: Optional[
        Callable[[ToolUseContext], ToolUseContext]
    ] = None
    mcp_meta: Optional[Dict[str, Any]] = None


# ── Tool definition ───────────────────────────────────────────────────


class Tool(abc.ABC, Generic[ToolInput, ToolOutput]):
    """Abstract tool matching Claude-Code's Tool interface.

    Subclasses define:
    - name, description, input_schema
    - call() — the main execution method
    - Optional metadata: is_concurrency_safe, is_read_only, etc.
    """

    # ── Required overrides ─────────────────────────────────────────

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Primary tool name."""

    @property
    def aliases(self) -> List[str]:
        """Optional aliases for backwards compatibility."""
        return []

    @property
    def search_hint(self) -> str:
        """Short capability phrase for keyword matching (3-10 words)."""
        return ""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Tool description shown to the model."""

    @property
    @abc.abstractmethod
    def input_schema(self) -> ToolInputJSONSchema:
        """JSON Schema for tool parameters."""

    @abc.abstractmethod
    async def call(
        self,
        args: ToolInput,
        context: ToolUseContext,
        on_progress: Optional[ToolCallProgress] = None,
    ) -> ToolResult[ToolOutput]:
        """Execute the tool with given arguments."""

    # ── Optional metadata with defaults ────────────────────────────

    def is_enabled(self) -> bool:
        """Whether this tool is available in the current environment."""
        return True

    def is_concurrency_safe(self, args: ToolInput) -> bool:
        """Whether multiple instances can run in parallel (read-only tools)."""
        return False

    def is_read_only(self, args: ToolInput) -> bool:
        """Whether this tool performs only reads (no side effects)."""
        return False

    def is_destructive(self, args: ToolInput) -> bool:
        """Whether this tool performs irreversible operations."""
        return False

    def should_defer(self) -> bool:
        """When True, tool is deferred and requires ToolSearch first."""
        return False

    def always_load(self) -> bool:
        """When True, tool is never deferred even when ToolSearch is enabled."""
        return False

    @property
    def strict(self) -> bool:
        """When True, API applies stricter schema enforcement."""
        return False

    @property
    def max_result_size_chars(self) -> int:
        """Max chars before result is persisted to disk; default 50k."""
        return 50000

    def get_path(self, args: ToolInput) -> Optional[str]:
        """Optional file path extraction for permission matching."""
        return None

    async def validate_input(
        self,
        args: ToolInput,
        context: ToolUseContext,
    ) -> ValidationResult:
        """Validate tool input before execution."""
        return ValidationResult.ok()

    async def check_permissions(
        self,
        args: ToolInput,
        context: ToolUseContext,
    ) -> PermissionResult:
        """Check if the tool is allowed to run with this input."""
        return PermissionResult(behavior="allow", updated_input=args)

    def interrupt_behavior(self) -> str:
        """'cancel' — stop on user interrupt; 'block' — keep running."""
        return "block"

    def is_open_world(self, args: ToolInput) -> bool:
        """Whether tool explores unknown state (web search, etc.)."""
        return False

    def requires_user_interaction(self) -> bool:
        """Whether tool needs direct user interaction."""
        return False

    @property
    def is_mcp(self) -> bool:
        """Whether this tool comes from an MCP server."""
        return False

    @property
    def is_lsp(self) -> bool:
        """Whether this tool uses LSP."""
        return False

    def user_facing_name(self, args: Optional[ToolInput] = None) -> str:
        """Human-readable name for UI display."""
        return self.name

    def get_tool_use_summary(
        self, args: Optional[ToolInput] = None
    ) -> Optional[str]:
        """Short summary for compact views."""
        return None

    def get_activity_description(
        self, args: Optional[ToolInput] = None
    ) -> Optional[str]:
        """Present-tense activity for spinner display."""
        return None

    async def prepare_permission_matcher(
        self, args: ToolInput
    ) -> Callable[[str], bool]:
        """Prepare a matcher for permission hook patterns."""
        return lambda pattern: pattern == self.name

    def to_auto_classifier_input(self, args: ToolInput) -> Any:
        """Input for the security classifier."""
        return ""

    # ── Utility ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tool metadata for API responses."""
        return {
            "name": self.name,
            "aliases": self.aliases,
            "description": self.description,
            "input_schema": self.input_schema,
            "search_hint": self.search_hint,
            "is_mcp": self.is_mcp,
        }


# ── build_tool factory ────────────────────────────────────────────────


DefaultableMethods = {
    "is_enabled",
    "is_concurrency_safe",
    "is_read_only",
    "is_destructive",
    "check_permissions",
    "to_auto_classifier_input",
    "user_facing_name",
}


def build_tool(
    name: str,
    *,
    aliases: Optional[List[str]] = None,
    search_hint: str = "",
    description: str = "",
    input_schema: Optional[ToolInputJSONSchema] = None,
    call_fn: Optional[Callable[..., Any]] = None,
    is_enabled_fn: Optional[Callable[[], bool]] = None,
    is_concurrency_safe_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    is_read_only_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    is_destructive_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    is_open_world_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    should_defer: bool = False,
    always_load: bool = False,
    strict: bool = False,
    max_result_size_chars: int = 50000,
    validate_input_fn: Optional[Callable[..., Any]] = None,
    check_permissions_fn: Optional[Callable[..., Any]] = None,
    interrupt_behavior: str = "block",
    user_facing_name: Optional[str] = None,
    get_path_fn: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
    get_activity_description_fn: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
    get_tool_use_summary_fn: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
) -> Tool:
    """Factory that creates a Tool subclass with safe defaults (mirrors buildTool()).

    Usage::

        read_tool = build_tool(
            name="Read",
            description="Read file contents",
            input_schema={...},
            call_fn=my_read_impl,
            is_read_only_fn=lambda _: True,
            is_concurrency_safe_fn=lambda _: True,
        )
    """
    _aliases = aliases or []
    _call_fn = call_fn
    _is_enabled = is_enabled_fn or (lambda: True)
    _is_concurrency_safe = is_concurrency_safe_fn or (lambda _: False)
    _is_read_only = is_read_only_fn or (lambda _: False)
    _is_destructive = is_destructive_fn or (lambda _: False)
    _is_open_world = is_open_world_fn or (lambda _: False)
    _validate_input = validate_input_fn
    _check_permissions = check_permissions_fn
    _get_path = get_path_fn
    _get_activity = get_activity_description_fn
    _get_summary = get_tool_use_summary_fn
    _user_facing_name = user_facing_name or name

    class _BuiltTool(Tool):
        @property
        def name(self) -> str:
            return name

        @property
        def aliases(self) -> List[str]:
            return _aliases

        @property
        def search_hint(self) -> str:
            return search_hint

        @property
        def description(self) -> str:
            return description

        @property
        def input_schema(self) -> ToolInputJSONSchema:
            return input_schema or {"type": "object", "properties": {}, "required": []}

        @property
        def strict(self) -> bool:
            return strict

        @property
        def max_result_size_chars(self) -> int:
            return max_result_size_chars

        def should_defer(self) -> bool:
            return should_defer

        def always_load(self) -> bool:
            return always_load

        def is_enabled(self) -> bool:
            return _is_enabled()

        def is_concurrency_safe(self, args: Any) -> bool:
            return _is_concurrency_safe(args)

        def is_read_only(self, args: Any) -> bool:
            return _is_read_only(args)

        def is_destructive(self, args: Any) -> bool:
            return _is_destructive(args)

        def is_open_world(self, args: Any) -> bool:
            return _is_open_world(args)

        def interrupt_behavior(self) -> str:
            return interrupt_behavior

        def user_facing_name(self, args: Optional[Any] = None) -> str:
            return _user_facing_name

        def get_path(self, args: Any) -> Optional[str]:
            if _get_path:
                return _get_path(args)
            return None

        def get_activity_description(self, args: Optional[Any] = None) -> Optional[str]:
            if _get_activity:
                return _get_activity(args or {})
            return None

        def get_tool_use_summary(self, args: Optional[Any] = None) -> Optional[str]:
            if _get_summary:
                return _get_summary(args or {})
            return None

        async def validate_input(
            self, args: Any, context: ToolUseContext
        ) -> ValidationResult:
            if _validate_input:
                return await _validate_input(args, context)
            return ValidationResult.ok()

        async def check_permissions(
            self, args: Any, context: ToolUseContext
        ) -> PermissionResult:
            if _check_permissions:
                return await _check_permissions(args, context)
            return PermissionResult(behavior="allow", updated_input=args)

        async def call(
            self,
            args: Any,
            context: ToolUseContext,
            on_progress: Optional[ToolCallProgress] = None,
        ) -> ToolResult:
            if _call_fn:
                return await _call_fn(args, context, on_progress)
            return ToolResult(data=f"[Tool {name} not implemented]")

        def to_auto_classifier_input(self, args: Any) -> Any:
            return json.dumps(args) if args else ""

    return _BuiltTool()


# ── Utility functions ─────────────────────────────────────────────────


def tool_matches_name(tool: Tool, name: str) -> bool:
    """Check if a tool's name or alias matches `name`."""
    return tool.name == name or name in tool.aliases


def find_tool_by_name(tools: Sequence[Tool], name: str) -> Optional[Tool]:
    """Find a tool by name or alias from a list of tools."""
    for t in tools:
        if tool_matches_name(t, name):
            return t
    return None


def filter_tools_by_deny_rules(
    tools: Sequence[Tool],
    permission_context: ToolPermissionContext,
) -> List[Tool]:
    """Filter out tools that have a blanket deny rule matching their name."""
    denied = set()
    for tool_name, rules in permission_context.always_deny_rules.items():
        # A rule with no specific content is a blanket deny
        if not rules:
            denied.add(tool_name)
    return [t for t in tools if t.name not in denied]


def assemble_tool_pool(
    builtin_tools: Sequence[Tool],
    mcp_tools: Sequence[Tool],
    permission_context: ToolPermissionContext,
) -> List[Tool]:
    """Combine built-in and MCP tools, deduplicate by name, filter by deny rules.

    Mirrors Claude-Code's assembleToolPool().
    """
    filtered_builtin = filter_tools_by_deny_rules(builtin_tools, permission_context)
    filtered_mcp = filter_tools_by_deny_rules(mcp_tools, permission_context)

    # Sort for stability, deduplicate by name (built-in wins)
    all_tools: List[Tool] = []
    seen_names: set = set()

    for t in sorted(filtered_builtin, key=lambda x: x.name):
        all_tools.append(t)
        seen_names.add(t.name)

    for t in sorted(filtered_mcp, key=lambda x: x.name):
        if t.name not in seen_names:
            all_tools.append(t)
            seen_names.add(t.name)

    return all_tools
