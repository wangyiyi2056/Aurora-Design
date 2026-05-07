"""TaskStopTool — stop a running task or sub-agent."""
from typing import Any, Dict

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TaskStop"
TOOL_DESCRIPTION = """Stop a running task or sub-agent execution.
Use this to terminate long-running or stuck tasks."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The ID of the task to stop.",
        },
    },
    "required": ["task_id"],
}


async def task_stop_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Stop a task by ID."""
    task_id = args.get("task_id", "")
    tasks = context.get_option("tasks", [])

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = "stopped"
            context.options["tasks"] = tasks
            return ToolResult(data=f"Task #{task_id} stopped.")

    return ToolResult(data=f"Error: Task #{task_id} not found")


async def task_stop_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("task_id"):
        return ValidationResult.fail("task_id is required")
    return ValidationResult.ok()


TaskStopTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=task_stop_call,
    validate_input_fn=task_stop_validate,
    is_concurrency_safe_fn=lambda _: False,
    is_read_only_fn=lambda _: False,
)
