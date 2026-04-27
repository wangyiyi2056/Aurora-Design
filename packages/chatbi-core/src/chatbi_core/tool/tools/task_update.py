"""TaskUpdateTool — update a task's properties in the task list."""
from typing import Any, Dict

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TaskUpdate"
TOOL_DESCRIPTION = """Update a task's status, subject, description, or dependencies.
Use this to mark tasks as in_progress or completed, or modify task metadata."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The ID of the task to update.",
        },
        "status": {
            "type": "string",
            "enum": ["pending", "in_progress", "completed"],
            "description": "New task status.",
        },
        "subject": {
            "type": "string",
            "description": "New task title.",
        },
        "description": {
            "type": "string",
            "description": "New task description.",
        },
        "add_blocked_by": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Task IDs that this task depends on.",
        },
    },
    "required": ["task_id"],
}


async def task_update_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Update a task."""
    task_id = args.get("task_id", "")
    tasks = context.get_option("tasks", [])

    for task in tasks:
        if task.get("id") == task_id:
            if "status" in args:
                task["status"] = args["status"]
            if "subject" in args:
                task["subject"] = args["subject"]
            if "description" in args:
                task["description"] = args["description"]
            context.options["tasks"] = tasks
            status = task.get("status", "pending")
            return ToolResult(data=f"Task #{task_id} updated to: {status}")

    return ToolResult(data=f"Error: Task #{task_id} not found")


async def task_update_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("task_id"):
        return ValidationResult.fail("task_id is required")
    status = args.get("status")
    if status and status not in ("pending", "in_progress", "completed"):
        return ValidationResult.fail(f"Invalid status: {status}")
    return ValidationResult.ok()


TaskUpdateTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=task_update_call,
    validate_input_fn=task_update_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: False,
)
