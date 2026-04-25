"""Hooks schema definitions."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class HookType(Enum):
    """Types of hooks in the agent lifecycle."""
    PRE_TOOL_USE = "PreToolUse"      # Before tool execution
    POST_TOOL_USE = "PostToolUse"    # After tool execution
    STOP = "Stop"                    # Session end
    SESSION_START = "SessionStart"   # Session start
    SESSION_END = "SessionEnd"       # Session end (alternative)
    USER_PROMPT_SUBMIT = "UserPromptSubmit"  # User input preprocessing


@dataclass
class HookMatcher:
    """Matcher for hook execution - matches tool names or patterns."""
    matcher: str  # Regex pattern or tool name (e.g., "Edit|Write", "Bash")
    hooks: List[Union[Callable, str]]  # Python functions or shell commands

    def matches(self, tool_name: str) -> bool:
        """Check if this matcher applies to a tool."""
        try:
            return bool(re.match(self.matcher, tool_name))
        except re.error:
            # Treat as literal match if regex fails
            return self.matcher == tool_name


@dataclass
class Hook:
    """A hook configuration entry."""
    type: HookType
    matchers: List[HookMatcher] = field(default_factory=list)
    description: Optional[str] = None
    enabled: bool = True

    def get_matching_hooks(
        self,
        tool_name: Optional[str] = None,
    ) -> List[Union[Callable, str]]:
        """Get hooks that match the given tool name."""
        if not self.enabled:
            return []

        matching: List[Union[Callable, str]] = []
        for matcher in self.matchers:
            if tool_name and matcher.matches(tool_name):
                matching.extend(matcher.hooks)
        return matching


@dataclass
class HookResult:
    """Result from hook execution."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    blocked: bool = False  # If True, the original action is blocked
    modified_input: Optional[Dict[str, Any]] = None  # Modified tool input