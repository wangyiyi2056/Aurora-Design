"""SkillTool — execute skills / slash commands within the session."""
from typing import Any, Dict, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "Skill"
TOOL_DESCRIPTION = """Execute a skill (slash command) in the current session.
Skills provide specialized capabilities like code review, testing,
architecture planning, and more. Use this to invoke registered skills."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "skill": {
            "type": "string",
            "description": "The skill name (e.g., 'review', 'test', 'plan').",
        },
        "args": {
            "type": "string",
            "description": "Optional arguments for the skill.",
        },
    },
    "required": ["skill"],
}


async def skill_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[Dict[str, Any]]:
    """Execute a skill by name."""
    skill_name = args.get("skill", "").strip().lstrip("/")
    skill_args = args.get("args", "")

    # Try to find and execute the skill via available tools/context
    skill_result = context.get_option("execute_skill")
    if skill_result:
        result = await skill_result(skill_name, skill_args)
        return ToolResult(data=result)

    # If no custom executor, return the skill info for the caller to handle
    return ToolResult(data={
        "success": True,
        "skill": skill_name,
        "status": "dispatched",
        "result": f"Skill '{skill_name}' is being processed.",
    })


async def skill_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    skill = args.get("skill", "").strip()
    if not skill:
        return ValidationResult.fail("skill name is required")
    return ValidationResult.ok()


SkillTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=skill_call,
    validate_input_fn=skill_validate,
    is_concurrency_safe_fn=lambda _: False,
    is_read_only_fn=lambda _: False,
    get_activity_description_fn=lambda args: f"Executing skill {args.get('skill', '')}",
)
