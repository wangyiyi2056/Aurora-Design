"""EditTool — edit file contents (find/replace). Ported from Claude-Code's FileEditTool."""
import difflib
import os
from pathlib import Path
from typing import Any, Dict, Optional

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Edit"
TOOL_DESCRIPTION = """Edit a file by making a targeted replacement.
Provide the text to find (old_string) and the replacement text (new_string).
Only the first occurrence will be replaced. Use unique context around the
text to ensure the correct match."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path to the file to edit.",
        },
        "old_string": {
            "type": "string",
            "description": "Text to search for (must be unique in the file).",
        },
        "new_string": {
            "type": "string",
            "description": "Text to replace it with.",
        },
    },
    "required": ["file_path", "old_string", "new_string"],
}


async def edit_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Edit a file by replacing text."""
    file_path = args.get("file_path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")

    path = Path(file_path)
    if not path.is_absolute():
        cwd = os.getcwd()
        path = Path(cwd) / path
        path = path.resolve()

    if not path.exists():
        return ToolResult(data=f"Error: File not found: {path}")

    original = path.read_text(encoding="utf-8")

    if old_string not in original:
        return ToolResult(
            data=f"Error: Could not find exact text to replace in {path}.\n"
            "Make sure the old_string matches exactly, including whitespace."
        )

    count = original.count(old_string)
    if count > 1:
        return ToolResult(
            data=f"Error: Found {count} occurrences of old_string in {path}. "
            "Please provide more unique context to ensure a single match."
        )

    new_content = original.replace(old_string, new_string, 1)
    path.write_text(new_content, encoding="utf-8")

    # Generate diff
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
    )
    diff_text = "".join(diff)

    return ToolResult(data=f"File edited: {path}\n\nDiff:\n{diff_text}")


async def edit_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("file_path"):
        return ValidationResult.fail("file_path is required")
    if not args.get("old_string"):
        return ValidationResult.fail("old_string is required")
    if "new_string" not in args:
        return ValidationResult.fail("new_string is required")
    return ValidationResult.ok()


def edit_is_destructive(args: Dict[str, Any]) -> bool:
    return True


EditTool = build_tool(
    name=TOOL_NAME,
    aliases=["FileEditTool"],
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=edit_call,
    validate_input_fn=edit_validate,
    is_concurrency_safe_fn=lambda _: False,
    is_read_only_fn=lambda _: False,
    is_destructive_fn=edit_is_destructive,
    get_path_fn=lambda args: args.get("file_path"),
    get_activity_description_fn=lambda args: f"Editing {args.get('file_path', '')}",
    get_tool_use_summary_fn=lambda args: f"Edit {args.get('file_path', '')}",
)
