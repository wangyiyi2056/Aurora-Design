"""TaskCreateTool — create a new task in the task list."""
from typing import Any, Dict

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "TaskCreate"
TOOL_DESCRIPTION = """Create a new task in the task list to track work progress.
Tasks support status tracking (pending/in_progress/completed),
dependencies (blocks/blockedBy), and arbitrary metadata."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {
            "type": "string",
            "description": "A brief title for the task.",
        },
        "description": {
            "type": "string",
            "description": "What needs to be done.",
        },
        "active_form": {
            "type": "string",
            "description": "Present continuous form (e.g., 'Running tests').",
        },
        "metadata": {
            "type": "object",
            "description": "Arbitrary metadata.",
        },
    },
    "required": ["subject", "description"],
}


async def task_create_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[Dict[str, Any]]:
    """Create a task in the task list."""
    import uuid

    subject = args.get("subject", "")
    description = args.get("description", "")
    active_form = args.get("active_form", "")

    tasks = context.get_option("tasks", [])
    task_id = str(uuid.uuid4())[:8]
    task = {
        "id": task_id,
        "subject": subject,
        "description": description,
        "active_form": active_form,
        "status": "pending",
    }
    tasks.append(task)
    context.options["tasks"] = tasks

    return ToolResult(data={"task": {"id": task_id, "subject": subject}})


async def task_create_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("subject"):
        return ValidationResult.fail("subject is required")
    if not args.get("description"):
        return ValidationResult.fail("description is required")
    return ValidationResult.ok()


TaskCreateTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=task_create_call,
    validate_input_fn=task_create_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: False,
)
