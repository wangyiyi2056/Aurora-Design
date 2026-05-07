"""TaskGetTool — get task details from the task list."""
from typing import Any, Dict

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TaskGet"
TOOL_DESCRIPTION = """Get the full details of a task by its ID.
Retrieves the task's subject, description, status,
blocking/blocked-by relationships, and metadata."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The ID of the task to retrieve.",
        },
    },
    "required": ["task_id"],
}


async def task_get_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Get a task by ID."""
    task_id = args.get("task_id", "")
    tasks = context.get_option("tasks", [])

    for task in tasks:
        if task.get("id") == task_id:
            return ToolResult(data=task)

    return ToolResult(data=f"Error: Task #{task_id} not found")


async def task_get_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("task_id"):
        return ValidationResult.fail("task_id is required")
    return ValidationResult.ok()


TaskGetTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=task_get_call,
    validate_input_fn=task_get_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
