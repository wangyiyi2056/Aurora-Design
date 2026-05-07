"""TodoWriteTool — manage the session task/checklist."""
from typing import Any, Dict, List

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TodoWrite"
TOOL_DESCRIPTION = """Update and manage the session todo list.
Use this to track progress on multi-step tasks by maintaining
a checklist of items with their completion status."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Description of the todo item."},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "Current status of the item.",
                    },
                },
                "required": ["content", "status"],
            },
            "description": "The updated todo list.",
        },
    },
    "required": ["todos"],
}


async def todo_write_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[Dict[str, Any]]:
    """Update the todo list in the session context."""
    todos = args.get("todos", [])

    old_todos = context.get_option("todos", [])
    context.options["todos"] = todos

    return ToolResult(data={
        "old_todos": old_todos,
        "new_todos": todos,
    })


async def todo_write_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    todos = args.get("todos", [])
    if not isinstance(todos, list):
        return ValidationResult.fail("todos must be a list")
    for item in todos:
        if "content" not in item:
            return ValidationResult.fail("Each todo item must have a 'content' field")
        if "status" not in item:
            return ValidationResult.fail("Each todo item must have a 'status' field")
        if item["status"] not in ("pending", "in_progress", "completed"):
            return ValidationResult.fail(f"Invalid status: {item['status']}")
    return ValidationResult.ok()


TodoWriteTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=todo_write_call,
    validate_input_fn=todo_write_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: False,
)
