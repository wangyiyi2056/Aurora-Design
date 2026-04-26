"""Plan mode enforcement — restricts tools to read-only during planning.

Mirrors Claude-Code's plan mode pattern:
- EnterPlanMode: sets mode to "plan", restricts to read-only tools
- ExitPlanMode: restores previous mode, accepts plan content
- In plan mode: only Read, Glob, Grep, LSP, WebFetch, WebSearch allowed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set


class PlanMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"


# Tools always allowed in plan mode (read-only exploration)
PLAN_MODE_ALLOWED_TOOLS: Set[str] = {
    "Read",
    "FileReadTool",
    "Glob",
    "Grep",
    "LSP",
    "WebFetch",
    "WebSearch",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
    "EnterPlanMode",
    "ExitPlanMode",
    "AskUserQuestion",
    "TodoWrite",
}

# Tools explicitly blocked in plan mode (write/destructive)
PLAN_MODE_BLOCKED_TOOLS: Set[str] = {
    "Write",
    "FileWriteTool",
    "Edit",
    "FileEditTool",
    "Bash",
    "NotebookEdit",
    "Agent",
    "SendMessage",
}


@dataclass
class PlanSession:
    """Tracks plan mode state and plan content."""

    mode: PlanMode = PlanMode.DEFAULT
    previous_mode: PlanMode = PlanMode.DEFAULT
    plan_content: str = ""
    files_explored: List[str] = field(default_factory=list)
    findings: str = ""


class PlanEnforcer:
    """Enforces plan mode restrictions on tool usage.

    Usage::

        enforcer = PlanEnforcer()
        if not enforcer.can_use_tool("Write", session):
            raise PermissionError("Write tool is blocked in plan mode")
    """

    def __init__(self):
        self.session = PlanSession()
        self._allowed_tools = PLAN_MODE_ALLOWED_TOOLS
        self._blocked_tools = PLAN_MODE_BLOCKED_TOOLS

    def enter_plan_mode(self) -> str:
        """Enter plan mode. Returns a guidance message."""
        if self.session.mode == PlanMode.PLAN:
            return "Already in plan mode."
        self.session.previous_mode = self.session.mode
        self.session.mode = PlanMode.PLAN
        self.session.plan_content = ""
        return (
            "Entered plan mode. Focus on exploration and design. "
            "Only read-only tools are available. "
            "Use ExitPlanMode when ready to present your plan."
        )

    def exit_plan_mode(self, plan: str = "") -> str:
        """Exit plan mode and restore previous mode. Returns confirmation."""
        if self.session.mode != PlanMode.PLAN:
            return "Not in plan mode."
        self.session.plan_content = plan
        self.session.mode = self.session.previous_mode
        self.session.previous_mode = PlanMode.DEFAULT
        return (
            f"Exited plan mode. Plan captured ({len(plan)} chars). "
            f"Restored {self.session.mode.value} mode."
        )

    def is_plan_mode(self) -> bool:
        """Check if currently in plan mode."""
        return self.session.mode == PlanMode.PLAN

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if a tool can be used in the current mode.

        In plan mode, only read-only tools are allowed.
        In default mode, all tools are allowed.
        """
        if self.session.mode != PlanMode.PLAN:
            return True

        # Explicit block takes priority
        if tool_name in self._blocked_tools:
            return False

        # Explicit allow list
        if tool_name in self._allowed_tools:
            return True

        # Unknown tools: block in plan mode (safety default)
        return False

    def get_blocked_message(self, tool_name: str) -> str:
        """Get a user-friendly message when a tool is blocked."""
        return (
            f"Tool '{tool_name}' is not available in plan mode. "
            f"Plan mode only allows read-only exploration tools. "
            f"Use ExitPlanMode to leave plan mode and execute writes/edits."
        )

    def track_exploration(self, file_path: str) -> None:
        """Track a file explored during plan mode."""
        if file_path not in self.session.files_explored:
            self.session.files_explored.append(file_path)

    def get_plan(self) -> str:
        """Get the accumulated plan content."""
        return self.session.plan_content

    def reset(self) -> None:
        """Reset plan session state."""
        self.session = PlanSession()
