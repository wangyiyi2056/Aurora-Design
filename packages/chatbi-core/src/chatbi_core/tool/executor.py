"""Single-tool executor — ported from Claude-Code's toolExecution.ts.

Provides run_tool_use() which handles the full lifecycle of a single
tool call: validation, permission check, execution, result handling.
"""

import json
import traceback
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from chatbi_core.tool.base import (
    Tool,
    ToolCallProgress,
    ToolProgress,
    ToolProgressData,
    ToolResult,
    ToolUseContext,
    ValidationResult,
    find_tool_by_name,
)


@dataclass
class ToolUseUpdate:
    """Yielded by run_tool_use() to communicate results and context changes."""
    message: Optional[Dict[str, Any]] = None
    context_modifier: Optional[Any] = None
    tool_use_id: Optional[str] = None


def _make_tool_result_message(
    tool_use_id: str,
    content: str,
    is_error: bool = False,
    tool_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a tool_result message compatible with the message schema."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            }
        ],
        "tool_use_result": content,
        "name": tool_name or "",
    }


def _make_progress_message(
    tool_use_id: str, data: ToolProgressData
) -> Dict[str, Any]:
    """Create a progress message."""
    return {
        "type": "progress",
        "data": data,
        "tool_use_id": tool_use_id,
    }


async def run_tool_use(
    tool_block: Dict[str, Any],
    tools: List[Tool],
    assistant_message_uuid: Optional[str] = None,
    context: Optional[ToolUseContext] = None,
) -> AsyncIterator[ToolUseUpdate]:
    """Execute a single tool call through its full lifecycle.

    Ported from runToolUse() in toolExecution.ts.

    Args:
        tool_block: Dict with 'name', 'id', 'input' keys (from model response).
        tools: Available tool definitions.
        assistant_message_uuid: UUID of the assistant message that produced this call.
        context: Execution context with permissions, abort control, etc.

    Yields:
        ToolUseUpdate with either a message (tool_result/progress) or context modifier.
    """
    tool_name = tool_block.get("name", "")
    tool_id = tool_block.get("id", "")
    tool_input = tool_block.get("input", {})

    if context is None:
        context = ToolUseContext()

    # Find the tool definition
    tool_def = find_tool_by_name(tools, tool_name)
    if not tool_def:
        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=f"<tool_use_error>Error: No such tool available: {tool_name}</tool_use_error>",
                is_error=True,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )
        return

    # Validate input
    validation = await tool_def.validate_input(tool_input, context)
    if not validation.success:
        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=f"<tool_use_error>Validation error: {validation.message}</tool_use_error>",
                is_error=True,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )
        return

    # Check permissions
    permission = await tool_def.check_permissions(tool_input, context)
    if permission.behavior == "deny":
        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=f"<tool_use_error>Permission denied: {permission.reason or 'Tool blocked by policy'}</tool_use_error>",
                is_error=True,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )
        return

    if permission.behavior == "ask":
        # In non-interactive mode, we deny by default for "ask" permissions
        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=f"<tool_use_error>Tool '{tool_name}' requires user approval</tool_use_error>",
                is_error=True,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )
        return

    # Use updated input from permission check
    final_input = permission.updated_input or tool_input

    # Progress callback
    progress_callback: ToolCallProgress = (
        lambda p: None
    )  # Will be wired to progress reporting

    # Execute
    try:
        result: ToolResult = await tool_def.call(
            final_input,
            context,
            on_progress=progress_callback,
        )

        # Serialize result data
        if isinstance(result.data, str):
            result_content = result.data
        else:
            try:
                result_content = json.dumps(result.data, ensure_ascii=False)
            except (TypeError, ValueError):
                result_content = str(result.data)

        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=result_content,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )

        # Yield context modifier if present
        if result.context_modifier is not None:
            yield ToolUseUpdate(
                context_modifier=result.context_modifier,
                tool_use_id=tool_id,
            )

        # Yield extra messages
        if result.new_messages:
            for msg in result.new_messages:
                yield ToolUseUpdate(message=msg, tool_use_id=tool_id)

    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"<tool_use_error>Error executing {tool_name}: {e}</tool_use_error>"
        yield ToolUseUpdate(
            message=_make_tool_result_message(
                tool_use_id=tool_id,
                content=error_msg,
                is_error=True,
                tool_name=tool_name,
            ),
            tool_use_id=tool_id,
        )
