"""App status data models.

Mirrors Claude-Code's StatusLineCommandInput JSON structure,
adapted for ChatBI's data analysis context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
class PermissionMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"
    ACCEPT_EDITS = "accept_edits"
    BYPASS = "bypass"


@dataclass
class ModelInfo:
    """Current model information."""
    id: str = ""
    display_name: str = ""
    provider: str = ""  # "openai", "anthropic", "kimi"


@dataclass
class ContextWindow:
    """Context window usage statistics."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    context_window_size: int = 200000
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def used_percentage(self) -> float:
        if self.context_window_size == 0:
            return 0.0
        total = self.total_input_tokens + self.total_output_tokens
        return round(total / self.context_window_size * 100, 1)

    @property
    def remaining_percentage(self) -> float:
        return round(100.0 - self.used_percentage, 1)


@dataclass
class CurrentUsage:
    """Current turn token usage (from latest API response)."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class CostStats:
    """Session cost statistics."""
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    total_api_duration_ms: int = 0
    total_tool_duration_ms: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0


@dataclass
class WorkspaceInfo:
    """Workspace information."""
    current_dir: str = ""
    project_dir: str = ""
    added_dirs: list = field(default_factory=list)


@dataclass
class ToolStats:
    """Tool execution statistics."""
    total_tool_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    active_tool_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_tool_calls == 0:
            return 100.0
        return round(self.successful_calls / self.total_tool_calls * 100, 1)


@dataclass
class GitInfo:
    """Git repository information."""
    branch: str = ""
    main_branch: str = ""
    has_uncommitted_changes: bool = False
    recent_commits: list = field(default_factory=list)


@dataclass
class MemoryStats:
    """Memory system statistics."""
    total_entries: int = 0
    user_memories: int = 0
    project_memories: int = 0
    feedback_entries: int = 0


@dataclass
class StatusData:
    """Complete application status snapshot.

    Mirrors Claude-Code's StatusLineCommandInput structure.
    """

    session_id: str = ""
    session_name: str = ""
    model: ModelInfo = field(default_factory=ModelInfo)
    context_window: ContextWindow = field(default_factory=ContextWindow)
    current_usage: CurrentUsage = field(default_factory=CurrentUsage)
    cost: CostStats = field(default_factory=CostStats)
    workspace: WorkspaceInfo = field(default_factory=WorkspaceInfo)
    tools: ToolStats = field(default_factory=ToolStats)
    git: GitInfo = field(default_factory=GitInfo)
    memory: MemoryStats = field(default_factory=MemoryStats)
    permission_mode: PermissionMode = PermissionMode.DEFAULT
    version: str = ""
    start_time: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "permission_mode": self.permission_mode.value,
            "version": self.version,
            "start_time": self.start_time,
            "model": {
                "id": self.model.id,
                "display_name": self.model.display_name,
                "provider": self.model.provider,
            },
            "context_window": {
                "total_input_tokens": self.context_window.total_input_tokens,
                "total_output_tokens": self.context_window.total_output_tokens,
                "context_window_size": self.context_window.context_window_size,
                "cache_creation_input_tokens": self.context_window.cache_creation_input_tokens,
                "cache_read_input_tokens": self.context_window.cache_read_input_tokens,
                "used_percentage": self.context_window.used_percentage,
                "remaining_percentage": self.context_window.remaining_percentage,
            },
            "current_usage": {
                "input_tokens": self.current_usage.input_tokens,
                "output_tokens": self.current_usage.output_tokens,
                "cache_creation_input_tokens": self.current_usage.cache_creation_input_tokens,
                "cache_read_input_tokens": self.current_usage.cache_read_input_tokens,
            },
            "cost": {
                "total_cost_usd": self.cost.total_cost_usd,
                "total_duration_ms": self.cost.total_duration_ms,
                "total_api_duration_ms": self.cost.total_api_duration_ms,
                "total_tool_duration_ms": self.cost.total_tool_duration_ms,
                "total_lines_added": self.cost.total_lines_added,
                "total_lines_removed": self.cost.total_lines_removed,
            },
            "workspace": {
                "current_dir": self.workspace.current_dir,
                "project_dir": self.workspace.project_dir,
                "added_dirs": self.workspace.added_dirs,
            },
            "tools": {
                "total_tool_calls": self.tools.total_tool_calls,
                "successful_calls": self.tools.successful_calls,
                "failed_calls": self.tools.failed_calls,
                "active_tool_count": self.tools.active_tool_count,
                "success_rate": self.tools.success_rate,
            },
            "git": {
                "branch": self.git.branch,
                "main_branch": self.git.main_branch,
                "has_uncommitted_changes": self.git.has_uncommitted_changes,
                "recent_commits": self.git.recent_commits,
            },
            "memory": {
                "total_entries": self.memory.total_entries,
                "user_memories": self.memory.user_memories,
                "project_memories": self.memory.project_memories,
                "feedback_entries": self.memory.feedback_entries,
            },
        }
