"""Permission Manager for ChatBI - manages permission checks."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chatbi_core.permissions.mode import PermissionMode
from chatbi_core.permissions.config import PermissionConfig


@dataclass
class PermissionDecision:
    """Result of a permission check."""
    allowed: bool
    needs_approval: bool
    reason: Optional[str] = None
    mode: PermissionMode = PermissionMode.DEFAULT


class PermissionManager:
    """Manages permission checks following Claude Code patterns.

    Hierarchical configuration:
    1. Organization-level policy (global)
    2. User-level settings (~/.chatbi/settings.json)
    3. Project-level settings (.chatbi/settings.json)

    Project settings override user, user overrides organization.
    """

    def __init__(
        self,
        global_settings_path: Optional[str] = None,
        project_settings_path: Optional[str] = None,
    ):
        self.global_settings_path = Path(
            global_settings_path or os.path.expanduser("~/.chatbi/settings.json")
        )
        self.project_settings_path = Path(project_settings_path) if project_settings_path else None

        self._configs: List[PermissionConfig] = []
        self._merged_config: Optional[PermissionConfig] = None
        self._load_configs()

    def _load_configs(self) -> None:
        """Load and merge configurations."""
        # Load global (user) settings
        global_config = PermissionConfig.load(str(self.global_settings_path))
        self._configs.append(global_config)

        # Load project settings (override global)
        if self.project_settings_path and self.project_settings_path.exists():
            try:
                import json
                data = json.loads(self.project_settings_path.read_text())
                permissions = data.get("permissions", {})
                project_config = PermissionConfig.from_dict(permissions)
                self._configs.append(project_config)
            except Exception:
                pass

        # Merge configs (project overrides user)
        self._merged_config = self._merge_configs()

    def _merge_configs(self) -> PermissionConfig:
        """Merge all configs with proper override."""
        if not self._configs:
            return PermissionConfig()

        # Start with first config (global)
        merged = PermissionConfig(
            mode=self._configs[0].mode,
            allowed_tools=self._configs[0].allowed_tools.copy(),
            allowed_commands=self._configs[0].allowed_commands.copy(),
            blocked_commands=self._configs[0].blocked_commands.copy(),
            require_approval_for=self._configs[0].require_approval_for.copy(),
            auto_approve_for=self._configs[0].auto_approve_for.copy(),
        )

        # Apply project overrides
        for config in self._configs[1:]:
            if config.mode != PermissionMode.DEFAULT:
                merged.mode = config.mode

            # Extend lists (project adds to allowed, overrides blocked)
            merged.allowed_tools.extend(config.allowed_tools)
            merged.allowed_commands.extend(config.allowed_commands)
            merged.blocked_commands.extend(config.blocked_commands)
            merged.require_approval_for.extend(config.require_approval_for)
            merged.auto_approve_for.extend(config.auto_approve_for)

        return merged

    def get_config(self) -> PermissionConfig:
        """Get merged permission configuration."""
        return self._merged_config or PermissionConfig()

    def set_mode(self, mode: PermissionMode) -> None:
        """Set permission mode."""
        if self._merged_config:
            self._merged_config.mode = mode

    def check_tool(self, tool_name: str) -> PermissionDecision:
        """Check if a tool can be used."""
        config = self.get_config()

        if not config.is_tool_allowed(tool_name):
            return PermissionDecision(
                allowed=False,
                needs_approval=False,
                reason=f"Tool '{tool_name}' not in allowed list",
                mode=config.mode,
            )

        # Check if needs approval based on mode
        needs_approval = config.mode.requires_approval("tool")

        return PermissionDecision(
            allowed=True,
            needs_approval=needs_approval,
            mode=config.mode,
        )

    def check_command(self, command: str) -> PermissionDecision:
        """Check if a command can be executed."""
        config = self.get_config()

        # Check blocked first
        if not config.is_command_allowed(command):
            return PermissionDecision(
                allowed=False,
                needs_approval=False,
                reason=f"Command blocked by policy",
                mode=config.mode,
            )

        # Check if needs approval
        needs_approval = config.needs_approval(command)

        return PermissionDecision(
            allowed=True,
            needs_approval=needs_approval,
            mode=config.mode,
        )

    def check_file_operation(
        self,
        operation: str,
        file_path: str,
    ) -> PermissionDecision:
        """Check if a file operation is allowed."""
        config = self.get_config()

        # Determine action type
        if operation in ("read", "glob", "grep"):
            action_type = "read"
        elif operation in ("edit", "write"):
            action_type = "edit"
        else:
            action_type = operation

        # Check if allowed
        needs_approval = config.mode.requires_approval(action_type)

        # Special handling for sensitive files
        sensitive_patterns = [
            ".env",
            "credentials",
            "secrets",
            "api_key",
            "password",
        ]

        for pattern in sensitive_patterns:
            if pattern in file_path.lower():
                needs_approval = True
                break

        return PermissionDecision(
            allowed=True,
            needs_approval=needs_approval,
            mode=config.mode,
        )

    def add_allowed_command(self, command: str) -> None:
        """Add a command to allowed list."""
        if self._merged_config:
            if command not in self._merged_config.allowed_commands:
                self._merged_config.allowed_commands.append(command)

    def add_blocked_command(self, command: str) -> None:
        """Add a command to blocked list."""
        if self._merged_config:
            if command not in self._merged_config.blocked_commands:
                self._merged_config.blocked_commands.append(command)

    def add_auto_approve(self, action: str) -> None:
        """Add an action to auto-approve list."""
        if self._merged_config:
            if action not in self._merged_config.auto_approve_for:
                self._merged_config.auto_approve_for.append(action)

    def save_project_config(self) -> None:
        """Save current config to project settings."""
        if not self.project_settings_path:
            return

        config = self.get_config()
        settings: Dict[str, Any] = {}

        if self.project_settings_path.exists():
            try:
                import json
                settings = json.loads(self.project_settings_path.read_text())
            except Exception:
                pass

        settings["permissions"] = config.to_dict()
        self.project_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.project_settings_path.write_text(json.dumps(settings))