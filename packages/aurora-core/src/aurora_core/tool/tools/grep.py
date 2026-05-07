"""GrepTool — search file contents. Ported from Claude-Code's GrepTool."""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Grep"
TOOL_DESCRIPTION = """Search file contents using regex patterns.
Use this to find code, configurations, or any text across the project.
Supports Python regex syntax. Results show file paths with line numbers."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Regex pattern to search for.",
        },
        "include": {
            "type": "string",
            "description": "File glob pattern to include (e.g., '*.py', '*.tsx').",
        },
        "path": {
            "type": "string",
            "description": "Root directory for the search (default: current directory).",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of matches (default: 50).",
        },
        "context_lines": {
            "type": "integer",
            "description": "Lines of context before/after each match (default: 0).",
        },
    },
    "required": ["pattern"],
}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".env",
    "dist", "build", ".next", ".ruff_cache", ".pytest_cache",
    ".gstack", ".aurora", "uploads", ".claude",
}


async def grep_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Search file contents using regex."""
    pattern_str = args.get("pattern", "")
    include = args.get("include", "*")
    root = args.get("path") or os.getcwd()
    max_results = args.get("max_results", 50)
    context_lines = args.get("context_lines", 0)

    root_path = Path(root).resolve()
    if not root_path.exists():
        return ToolResult(data=f"Error: Path not found: {root}")

    try:
        regex = re.compile(pattern_str)
    except re.error as e:
        return ToolResult(data=f"Error: Invalid regex pattern: {e}")

    results: List[str] = []
    total_matches = 0

    for file_path in root_path.rglob(include):
        if file_path.is_dir() or file_path.is_symlink():
            continue

        # Skip ignored directories
        rel = file_path.relative_to(root_path)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue

        # Skip binary files
        try:
            if not _is_text_file(file_path):
                continue
        except Exception:
            continue

        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").split("\n")
        except Exception:
            continue

        for i, line in enumerate(lines):
            if regex.search(line):
                total_matches += 1
                if total_matches > max_results:
                    results.append("... [truncated, too many results]")
                    break

                prefix = f"{rel}:{i + 1}:"
                results.append(f"{prefix} {line}")

                # Context lines
                if context_lines > 0:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    for ci in range(start, end):
                        if ci != i:
                            marker = " " if ci < i else " "
                            results.append(f"  {marker} {ci + 1}: {lines[ci]}")
                    results.append("---")

        if total_matches > max_results:
            break

    if not results:
        return ToolResult(data=f"No matches for '{pattern_str}' in {root_path}")

    return ToolResult(data="\n".join(results))


def _is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file."""
    text_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
        ".toml", ".cfg", ".ini", ".md", ".txt", ".rst", ".html", ".css",
        ".scss", ".less", ".xml", ".svg", ".env", ".sh", ".bash", ".zsh",
        ".sql", ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".c",
        ".cpp", ".h", ".hpp", ".vue", ".svelte", ".pyx", ".pxd",
        ".dockerfile", ".gitignore", ".gitattributes", ".editorconfig",
        ".npmrc", ".babelrc", ".eslintrc", ".prettierrc",
    }
    return path.suffix.lower() in text_extensions


async def grep_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("pattern"):
        return ValidationResult.fail("pattern is required")

    # Validate regex
    try:
        re.compile(args["pattern"])
    except re.error as e:
        return ValidationResult.fail(f"Invalid regex: {e}")

    return ValidationResult.ok()


GrepTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=grep_call,
    validate_input_fn=grep_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    get_activity_description_fn=lambda args: f"Grep: {args.get('pattern', '')}",
    get_tool_use_summary_fn=lambda args: f"Grep {args.get('pattern', '')}",
)
