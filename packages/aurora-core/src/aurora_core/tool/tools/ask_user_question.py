"""AskUserQuestionTool — prompt the user with a multiple-choice question."""
from typing import Any, Dict

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "AskUserQuestion"
TOOL_DESCRIPTION = """Ask the user a multi-choice question and collect their response.
Use this to get user input on decisions, preferences, or clarifications.
The user will be presented with 2-4 options to choose from."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question to ask the user.",
        },
        "header": {
            "type": "string",
            "description": "Short label/tag for the question (e.g., 'Approach', 'Library').",
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Option display text (1-5 words)."},
                    "description": {"type": "string", "description": "Explanation of this option."},
                },
                "required": ["label", "description"],
            },
            "minItems": 2,
            "maxItems": 4,
            "description": "Available choices (2-4 options).",
        },
        "multi_select": {
            "type": "boolean",
            "description": "Allow selecting multiple options.",
        },
    },
    "required": ["question", "options"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "answers": {"type": "array", "items": {"type": "string"}},
    },
}


async def ask_user_question_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[Dict[str, Any]]:
    """Ask a question and return user answers from context."""
    question = args.get("question", "")
    options = args.get("options", [])
    multi_select = args.get("multi_select", False)

    user_answers = context.get_option("user_answers", {})
    answers = user_answers.get(question, [])

    if not answers:
        return ToolResult(data={
            "question": question,
            "answers": [],
            "status": "pending",
            "options": options,
            "multi_select": multi_select,
        })

    return ToolResult(data={
        "question": question,
        "answers": answers if isinstance(answers, list) else [answers],
    })


async def ask_user_question_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("question"):
        return ValidationResult.fail("question is required")
    options = args.get("options", [])
    if len(options) < 2:
        return ValidationResult.fail("At least 2 options are required")
    if len(options) > 4:
        return ValidationResult.fail("At most 4 options are allowed")
    return ValidationResult.ok()


AskUserQuestionTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=ask_user_question_call,
    validate_input_fn=ask_user_question_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
)
