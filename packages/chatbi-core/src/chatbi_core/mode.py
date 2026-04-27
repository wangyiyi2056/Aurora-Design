"""Operational mode for ChatBI — BI (web, read-only analysis) vs CODE (desktop, full tools).

Mirrors Claude Code's cowork concept: different environments get different
tool sets and system prompts.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from chatbi_core.tool.base import Tool


class ChatMode(Enum):
    """Operational mode for the ChatBI service.

    BI: Web browser / file analysis mode. Read-only + analytics tools,
        BI-focused system prompt. No shell, file writes, or code editing.
    CODE: Electron / desktop mode. Full Claude Code engineering tool set
        plus the original software-engineering system prompt.
    """

    BI = "bi"
    CODE = "code"

    @classmethod
    def detect(cls, ext_info: Optional[Dict[str, Any]] = None) -> "ChatMode":
        """Detect mode from ext_info.client_type.

        Defaults to CODE for backward compatibility with existing deployments.
        """
        if ext_info and ext_info.get("client_type") == "web":
            return cls.BI
        return cls.CODE


# Tools allowed in BI mode (web browser — no filesystem/shell access)
BI_ALLOWED_TOOLS: frozenset = frozenset(
    {
        "Read",  # read uploaded files
        "WebFetch",  # fetch web content
        "WebSearch",  # search the web
        "Skill",  # invoke analytical skills
        "TaskCreate",
        "TaskGet",
        "TaskUpdate",
        "TaskList",
        "TaskStop",
        "TodoWrite",
        "SendMessage",
        "NotebookEdit",
        "AskUserQuestion",
    }
)

# Tools ONLY available in CODE mode (require filesystem/shell)
CODE_ONLY_TOOLS: frozenset = frozenset(
    {
        "Bash",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "Agent",
        "TaskOutput",
        "EnterPlanMode",
        "ExitPlanMode",
        "LSP",
    }
)


def filter_tools_for_mode(tools: Sequence[Tool], mode: ChatMode) -> List[Tool]:
    """Filter tools based on operational mode.

    BI mode: only tools in BI_ALLOWED_TOOLS
    CODE mode: all tools pass through
    """
    if mode == ChatMode.CODE:
        return list(tools)
    return [t for t in tools if t.name in BI_ALLOWED_TOOLS]
