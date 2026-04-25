"""Permission Configuration for ChatBI."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbi_core.permissions.mode import PermissionMode


@dataclass
class PermissionConfig:
    """Configuration for permissions system.

    Supports hierarchical settings:
    - Organization level (global policy)
    - Project level (.chatbi/settings.json)
    - User level (~/.chatbi/settings.json)
    """

    mode: PermissionMode = PermissionMode.DEFAULT
    allowed_tools: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    require_approval_for: List[str] = field(default_factory=list)
    auto_approve_for: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "allowed_tools": self.allowed_tools,
            "allowed_commands": self.allowed_commands,
            "blocked_commands": self.blocked_commands,
            "require_approval_for": self.require_approval_for,
            "auto_approve_for": self.auto_approve_for,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionConfig":
        """Create from dictionary."""
        mode_str = data.get("mode", "default")
        try:
            mode = PermissionMode(mode_str)
        except ValueError:
            mode = PermissionMode.DEFAULT

        return cls(
            mode=mode,
            allowed_tools=data.get("allowed_tools", []),
            allowed_commands=data.get("allowed_commands", []),
            blocked_commands=data.get("blocked_commands", []),
            require_approval_for=data.get("require_approval_for", []),
            auto_approve_for=data.get("auto_approve_for", []),
        )

    @classmethod
    def load(cls, path: Optional[str] = None) -> "PermissionConfig":
        """Load from settings file."""
        settings_path = Path(path or os.path.expanduser("~/.chatbi/settings.json"))

        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                permissions = data.get("permissions", {})
                return cls.from_dict(permissions)
            except json.JSONDecodeError:
                pass

        return cls()

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is in allowed list."""
        if self.allowed_tools:
            return tool_name in self.allowed_tools
        return True  # Allow all if not specified

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed."""
        # Check blocked first
        for blocked in self.blocked_commands:
            if blocked in command:
                return False

        # Check allowed
        if self.allowed_commands:
            for allowed in self.allowed_commands:
                if allowed in command:
                    return True
            return False

        return True  # Allow if not specified

    def needs_approval(self, action: str) -> bool:
        """Check if an action needs explicit approval."""
        if action in self.auto_approve_for:
            return False
        if action in self.require_approval_for:
            return True
        return self.mode.requires_approval(action)