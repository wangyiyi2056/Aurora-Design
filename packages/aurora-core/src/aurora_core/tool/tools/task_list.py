"""TaskListTool — list all tasks in the current session."""
from typing import Any, Dict

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TaskList"
TOOL_DESCRIPTION = """List all tasks in the current session.
Returns a summary of each task with its status, subject, and ID.
Use this to track overall progress on multi-step work."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


async def task_list_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """List all tasks."""
    tasks = context.get_option("tasks", [])

    if not tasks:
        return ToolResult(data="No tasks in the current session.")

    lines = [f"{'ID':<10} {'Status':<14} Subject"]
    lines.append("-" * 60)
    for task in tasks:
        tid = task.get("id", "?")
        status = task.get("status", "?")
        subject = task.get("subject", "?")
        lines.append(f"{tid:<10} {status:<14} {subject}")

    return ToolResult(data="\n".join(lines))


TaskListTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=task_list_call,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
