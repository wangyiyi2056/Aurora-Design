"""EnterPlanModeTool — switch to plan mode for exploration and design."""
from typing import Any, Dict

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "EnterPlanMode"
TOOL_DESCRIPTION = """Switch to plan mode for complex tasks requiring exploration and design.
In plan mode, focus on understanding the codebase and designing an approach
before writing any code. Use ExitPlanMode when ready to present the plan."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


async def enter_plan_mode_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Enter plan mode by setting the session mode to 'plan'."""
    from aurora_core.tool.base import ToolPermissionContext

    if context.get_option("agent_id"):
        raise RuntimeError("EnterPlanMode cannot be used in sub-agent contexts")

    # Update permission context to plan mode
    ctx = context.permission_context
    context.permission_context = ToolPermissionContext(
        mode="plan",
        always_allow_rules=ctx.always_allow_rules,
        always_deny_rules=ctx.always_deny_rules,
        always_ask_rules=ctx.always_ask_rules,
    )

    return ToolResult(data="Entered plan mode. Focus on exploration and design — do not write code.")


EnterPlanModeTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=enter_plan_mode_call,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
