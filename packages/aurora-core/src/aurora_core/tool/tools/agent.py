"""AgentTool — spawn sub-agents. Ported from Claude-Code's AgentTool."""
from typing import Any, Dict, Optional

from aurora_core.tool.base import (
    AgentProgress,
    ToolCallProgress,
    ToolProgress,
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Agent"
TOOL_DESCRIPTION = """Spawn a sub-agent to work on a task independently.
Sub-agents get their own context and can use tools to complete their work.
Use this for tasks that benefit from parallel execution or focused attention."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "The task description for the sub-agent.",
        },
        "subagent_name": {
            "type": "string",
            "description": "Name of the subagent definition to use (optional).",
        },
    },
    "required": ["task"],
}


async def agent_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress: Optional[ToolCallProgress] = None,
) -> ToolResult[str]:
    """Execute a sub-agent to complete a task."""
    task = args.get("task", "")
    subagent_name = args.get("subagent_name", "")

    # Find subagent manager in context options
    subagent_manager = context.options.get("subagent_manager")
    if not subagent_manager:
        return ToolResult(data="Error: No subagent manager available in context")

    # Find LLM client in context options
    llm_client = context.options.get("llm_client")
    if not llm_client:
        return ToolResult(data="Error: No LLM client available in context")

    # Report progress
    if on_progress:
        on_progress(ToolProgress(
            tool_use_id=context.tool_use_id or "",
            data=AgentProgress(
                task=task[:100],
                subagent_name=subagent_name or "default",
                status="running",
            ),
        ))

    # Execute subagent
    result = await subagent_manager.execute(
        name=subagent_name or "default",
        task=task,
        llm_client=llm_client,
        skill_registry=context.options.get("skill_registry"),
    )

    if result.success:
        return ToolResult(
            data=f"## Sub-agent Result: {result.subagent_name}\n\n{result.summary}\n\n"
            f"*Tools used: {', '.join(result.tools_used)}*\n"
            f"*Execution time: {result.execution_time:.1f}s*"
        )
    else:
        return ToolResult(data=f"Sub-agent error: {result.error or 'Unknown error'}")


async def agent_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("task"):
        return ValidationResult.fail("task is required")
    return ValidationResult.ok()


AgentTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=agent_call,
    validate_input_fn=agent_validate,
    is_concurrency_safe_fn=lambda _: False,
    is_read_only_fn=lambda _: False,
    interrupt_behavior="block",
    get_activity_description_fn=lambda args: f"Agent: {args.get('task', '')[:60]}",
    get_tool_use_summary_fn=lambda args: f"Agent task: {args.get('task', '')[:80]}",
)
