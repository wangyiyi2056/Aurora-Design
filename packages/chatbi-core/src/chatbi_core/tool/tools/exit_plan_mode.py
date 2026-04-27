"""ExitPlanModeTool — exit plan mode and present the plan for approval."""
from typing import Any, Dict

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "ExitPlanMode"
TOOL_DESCRIPTION = """Exit plan mode and present the implementation plan for approval.
Call this after exploring the codebase and designing the approach.
The plan will be presented to the user for review."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "string",
            "description": "The implementation plan to present for approval.",
        },
    },
    "required": ["plan"],
}


async def exit_plan_mode_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Exit plan mode and return the plan."""
    plan = args.get("plan", "")

    # Restore permission context to default
    from chatbi_core.tool.base import ToolPermissionContext

    ctx = context.permission_context
    context.permission_context = ToolPermissionContext(
        mode="default",
        always_allow_rules=ctx.always_allow_rules,
        always_deny_rules=ctx.always_deny_rules,
        always_ask_rules=ctx.always_ask_rules,
    )

    return ToolResult(data=f"Plan submitted for approval:\n\n{plan}")


async def exit_plan_mode_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("plan", "").strip():
        return ValidationResult.fail("plan is required and must not be empty")
    return ValidationResult.ok()


ExitPlanModeTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=exit_plan_mode_call,
    validate_input_fn=exit_plan_mode_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
