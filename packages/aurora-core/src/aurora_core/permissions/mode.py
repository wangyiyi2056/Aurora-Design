"""Permission Mode definitions for Aurora."""

from enum import Enum


class PermissionMode(Enum):
    """Permission modes following Claude Code patterns.

    Modes:
    - default: Ask before file edits and shell commands
    - acceptEdits: Auto-accept file edits, ask for other commands
    - plan: Read-only tools only, create plan for approval
    - auto: Evaluate with background safety checks (research preview)
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    AUTO = "auto"

    def is_read_only(self) -> bool:
        """Check if this mode only allows read operations."""
        return self == PermissionMode.PLAN

    def auto_accepts_edits(self) -> bool:
        """Check if this mode auto-accepts file edits."""
        return self == PermissionMode.ACCEPT_EDITS or self == PermissionMode.AUTO

    def requires_approval(self, action_type: str) -> bool:
        """Check if a specific action type requires approval."""
        if self == PermissionMode.AUTO:
            return False  # Background checks handle this

        if self == PermissionMode.ACCEPT_EDITS:
            # Auto-accept file operations, ask for others
            return action_type not in ("read", "edit", "write")

        if self == PermissionMode.PLAN:
            # Only allow read operations
            return action_type != "read"

        # Default: ask for everything
        return True