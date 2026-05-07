"""WriteTool — write file contents. Ported from Claude-Code's FileWriteTool."""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Write"
TOOL_DESCRIPTION = """Write content to a file, creating it if it doesn't exist.
Use this to create new files or overwrite existing ones.
The file and its parent directories will be created automatically."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path where the file will be written.",
        },
        "content": {
            "type": "string",
            "description": "Full content to write to the file.",
        },
    },
    "required": ["file_path", "content"],
}


async def write_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Write content to a file."""
    file_path = args.get("file_path", "")
    content = args.get("content", "")

    path = Path(file_path)
    if not path.is_absolute():
        cwd = os.getcwd()
        path = Path(cwd) / path
        path = path.resolve()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    size = len(content.encode("utf-8"))
    return ToolResult(data=f"Written {size} bytes to {path}")


async def write_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("file_path"):
        return ValidationResult.fail("file_path is required")
    if args.get("content") is None:
        return ValidationResult.fail("content is required")
    return ValidationResult.ok()


def write_is_destructive(args: Dict[str, Any]) -> bool:
    return True


WriteTool = build_tool(
    name=TOOL_NAME,
    aliases=["FileWriteTool"],
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=write_call,
    validate_input_fn=write_validate,
    is_read_only_fn=lambda _: False,
    is_destructive_fn=write_is_destructive,
    get_path_fn=lambda args: args.get("file_path"),
    get_activity_description_fn=lambda args: f"Writing to {args.get('file_path', '')}",
    get_tool_use_summary_fn=lambda args: f"Write {args.get('file_path', '')}",
)
