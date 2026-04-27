"""ReadTool — read file contents. Ported from Claude-Code's FileReadTool."""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Read"
TOOL_DESCRIPTION = """Read the contents of a file.
Use this to view file contents, read code, check configuration, etc.
Supports text files, with line numbers added for reference."""
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Absolute or relative path to the file to read.",
        },
        "offset": {
            "type": "integer",
            "description": "Line number to start from (1-based, default: 1).",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of lines to read.",
        },
    },
    "required": ["file_path"],
}

MAX_FILE_SIZE = 1024 * 1024  # 1MB


async def read_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Read a file and return its contents."""
    file_path = args.get("file_path", "")
    offset = args.get("offset", 0)
    limit = args.get("limit", 0)

    path = Path(file_path)
    if not path.is_absolute():
        cwd = os.getcwd()
        path = Path(cwd) / path
        path = path.resolve()

    if not path.exists():
        return ToolResult(data=f"Error: File not found: {path}")
    if not path.is_file():
        return ToolResult(data=f"Error: Not a file: {path}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return ToolResult(
            data=f"Error: File too large ({file_size / 1024 / 1024:.1f}MB). Max: 1MB"
        )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ToolResult(data=f"Error reading file: {e}")

    lines = text.split("\n")
    if offset:
        lines = lines[offset - 1:]
    if limit:
        lines = lines[:limit]

    # Add line numbers
    numbered = []
    start = offset or 1
    for i, line in enumerate(lines, start=start):
        numbered.append(f"{i:>6}\t{line}")

    return ToolResult(data="\n".join(numbered))


async def read_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    file_path = args.get("file_path", "")
    if not file_path:
        return ValidationResult.fail("file_path is required")
    return ValidationResult.ok()


ReadTool = build_tool(
    name=TOOL_NAME,
    aliases=["FileReadTool"],
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=read_call,
    validate_input_fn=read_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    get_path_fn=lambda args: args.get("file_path"),
    get_activity_description_fn=lambda args: f"Reading {args.get('file_path', '')}",
    get_tool_use_summary_fn=lambda args: f"Read {args.get('file_path', '')}",
)
