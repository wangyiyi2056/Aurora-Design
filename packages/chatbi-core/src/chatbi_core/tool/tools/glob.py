"""GlobTool — file pattern matching. Ported from Claude-Code's GlobTool."""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Glob"
TOOL_DESCRIPTION = """Find files matching a glob pattern.
Supports ** (recursive), * (wildcard), ? (single char), [abc] (character class).
Use this to find files by name pattern, extension, or directory structure."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Glob pattern to match (e.g., '**/*.py', 'src/**/*.tsx').",
        },
        "path": {
            "type": "string",
            "description": "Root directory for the search (default: current directory).",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results (default: 100).",
        },
    },
    "required": ["pattern"],
}


async def glob_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Find files matching a glob pattern."""
    pattern = args.get("pattern", "")
    root = args.get("path") or os.getcwd()
    max_results = args.get("max_results", 100)

    root_path = Path(root).resolve()
    if not root_path.exists():
        return ToolResult(data=f"Error: Path not found: {root}")

    # Use pathlib's glob
    matches: List[str] = []
    try:
        for p in root_path.rglob(pattern):
            if len(matches) >= max_results:
                matches.append("... [truncated, too many results]")
                break
            matches.append(str(p.relative_to(root_path)))
    except Exception as e:
        return ToolResult(data=f"Error during glob: {e}")

    matches.sort()
    if not matches:
        return ToolResult(data=f"No files matching '{pattern}' in {root_path}")

    result = "\n".join(matches)
    return ToolResult(data=result)


async def glob_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("pattern"):
        return ValidationResult.fail("pattern is required")
    return ValidationResult.ok()


GlobTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=glob_call,
    validate_input_fn=glob_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    get_activity_description_fn=lambda args: f"Glob: {args.get('pattern', '')}",
    get_tool_use_summary_fn=lambda args: f"Glob {args.get('pattern', '')}",
)
