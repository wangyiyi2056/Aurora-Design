"""LSPTool — Language Server Protocol integration for code intelligence."""
from typing import Any, Dict, List, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "LSP"
TOOL_DESCRIPTION = """Use Language Server Protocol (LSP) for code intelligence.
Supports go-to-definition, find-references, hover info, and symbol search.
LSP servers must be configured for the relevant programming language."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": [
                "goToDefinition", "findReferences", "hover",
                "documentSymbol", "workspaceSymbol", "goToImplementation",
            ],
            "description": "LSP operation to perform.",
        },
        "file_path": {
            "type": "string",
            "description": "Path to the file (required for file-scoped operations).",
        },
        "line": {
            "type": "integer",
            "description": "Line number (1-based).",
        },
        "character": {
            "type": "integer",
            "description": "Character offset (1-based).",
        },
        "query": {
            "type": "string",
            "description": "Search query (for workspaceSymbol).",
        },
    },
    "required": ["operation"],
}


async def lsp_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Execute an LSP operation."""
    operation = args.get("operation", "")
    file_path = args.get("file_path", "")
    line = args.get("line", 0)
    character = args.get("character", 0)
    query = args.get("query", "")

    # Try LSP handler from context first, then fall back to global handler
    lsp_fn = context.get_option("lsp_execute")
    if lsp_fn:
        result = await lsp_fn(operation, file_path, line, character, query)
        return ToolResult(data=result)

    # Use global LSP handler (Jedi-based)
    from aurora_core.lsp import execute_lsp
    project_root = context.get_option("project_root", "")
    result = execute_lsp(
        operation=operation,
        file_path=file_path,
        line=int(line),
        character=int(character),
        query=query,
        project_root=project_root or None,
    )
    return ToolResult(data=result)


async def lsp_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    operation = args.get("operation", "")
    valid_ops = {
        "goToDefinition", "findReferences", "hover",
        "documentSymbol", "workspaceSymbol", "goToImplementation",
    }
    if operation not in valid_ops:
        return ValidationResult.fail(f"Invalid operation: {operation}")
    if operation in ("goToDefinition", "findReferences", "hover", "goToImplementation", "documentSymbol"):
        if not args.get("file_path"):
            return ValidationResult.fail(f"file_path is required for {operation}")
    if operation == "workspaceSymbol" and not args.get("query"):
        return ValidationResult.fail("query is required for workspaceSymbol")
    return ValidationResult.ok()


LSPTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=lsp_call,
    validate_input_fn=lsp_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
