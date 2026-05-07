"""Task tools — task management. Ported from Claude-Code's TaskOutputTool."""

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TASK_OUTPUT_NAME = "TaskOutput"
TASK_OUTPUT_DESCRIPTION = """Get the output from a previously executed sub-agent or task.
Use this to retrieve results from parallel task executions."""


TASK_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The task ID to get output from.",
        },
    },
    "required": ["task_id"],
}


async def task_output_call(args, context, on_progress=None):
    task_id = args.get("task_id", "")
    return ToolResult(data=f"[TaskOutput is not yet implemented. Task ID: {task_id}]")


TaskOutputTool = build_tool(
    name=TASK_OUTPUT_NAME,
    description=TASK_OUTPUT_DESCRIPTION,
    input_schema=TASK_OUTPUT_SCHEMA,
    call_fn=task_output_call,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    get_activity_description_fn=lambda args: f"Getting output for task {args.get('task_id', '')}",
)
