"""SendMessageTool — send messages between sub-agents (team communication)."""
from typing import Any, Dict, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "SendMessage"
TOOL_DESCRIPTION = """Send a message to another agent or sub-agent in the session.
Use this for inter-agent communication when running parallel tasks.
Messages are delivered asynchronously to the recipient's inbox."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {
            "type": "string",
            "description": "Recipient agent name or '*' for broadcast.",
        },
        "message": {
            "type": "string",
            "description": "Message content to send.",
        },
        "summary": {
            "type": "string",
            "description": "Short summary shown as a preview.",
        },
    },
    "required": ["to", "message"],
}


async def send_message_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[Dict[str, Any]]:
    """Send a message to another agent."""
    recipient = args.get("to", "")
    message = args.get("message", "")
    summary = args.get("summary", "")

    # Dispatch message via context if available
    send_fn = context.get_option("send_message")
    if send_fn:
        result = await send_fn(recipient, message, summary)
        return ToolResult(data=result)

    return ToolResult(data={
        "success": True,
        "message": f"Message queued for {recipient}",
        "recipient": recipient,
    })


async def send_message_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    to = args.get("to", "")
    if not to:
        return ValidationResult.fail("'to' is required")
    if "@" in to:
        return ValidationResult.fail("'to' must be a bare agent name, not an address")
    if not args.get("message"):
        return ValidationResult.fail("'message' is required")
    return ValidationResult.ok()


SendMessageTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=send_message_call,
    validate_input_fn=send_message_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: False,
)
