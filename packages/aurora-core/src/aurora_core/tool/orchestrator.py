"""Tool orchestration — ported from Claude-Code's toolOrchestration.ts.

Provides:
- partition_tool_calls() — groups tools into concurrency-safe batches
- run_tools() — executes batches with proper concurrency control
"""

from typing import Any, AsyncGenerator, Dict, List, Tuple

from aurora_core.tool.base import (
    Tool,
    ToolUseContext,
    find_tool_by_name,
)
from aurora_core.tool.executor import ToolUseUpdate, run_tool_use


async def run_tools(
    tool_blocks: List[Dict[str, Any]],
    tools: List[Tool],
    assistant_message_uuid: str,
    context: ToolUseContext,
) -> AsyncGenerator[ToolUseUpdate, None]:
    """Execute tool calls respecting concurrency semantics.

    Ported from runTools() in toolOrchestration.ts.

    Concurrency-safe tools (reads) run in parallel batches.
    Non-concurrent tools run serially, one at a time.
    """
    current_context = context

    for is_concurrency_safe, blocks in partition_tool_calls(tool_blocks, tools):
        if is_concurrency_safe:
            # Run read-only batch concurrently
            async for update in _run_tools_concurrently(
                blocks, tools, assistant_message_uuid, current_context
            ):
                yield update
        else:
            # Run non-read-only batch serially
            async for update in _run_tools_serially(
                blocks, tools, assistant_message_uuid, current_context
            ):
                yield update


def partition_tool_calls(
    tool_blocks: List[Dict[str, Any]],
    tools: List[Tool],
) -> List[Tuple[bool, List[Dict[str, Any]]]]:
    """Partition tools into concurrency-safe and non-concurrent batches.

    Ported from partitionToolCalls() in toolOrchestration.ts.

    Returns list of (is_concurrency_safe, [blocks]) tuples.
    """
    if not tool_blocks:
        return []

    batches: List[Tuple[bool, List[Dict[str, Any]]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_is_concurrency_safe: bool = False

    for block in tool_blocks:
        tool_def = find_tool_by_name(tools, block.get("name", ""))
        is_safe = False
        if tool_def:
            try:
                is_safe = tool_def.is_concurrency_safe(block.get("input", {}))
            except Exception:
                is_safe = False

        if not current_batch:
            current_is_concurrency_safe = is_safe
            current_batch.append(block)
        elif current_is_concurrency_safe == is_safe:
            # Same concurrency type → same batch
            if is_safe:
                # Concurrent-safe tools can keep growing
                current_batch.append(block)
            else:
                # Non-concurrent tools: each gets its own batch
                batches.append((False, current_batch))
                current_batch = [block]
                current_is_concurrency_safe = False
        else:
            # Concurrency type changed
            batches.append((current_is_concurrency_safe, current_batch))
            current_batch = [block]
            current_is_concurrency_safe = is_safe

    if current_batch:
        batches.append((current_is_concurrency_safe, current_batch))

    return batches


async def _run_tools_concurrently(
    blocks: List[Dict[str, Any]],
    tools: List[Tool],
    assistant_message_uuid: str,
    context: ToolUseContext,
) -> AsyncGenerator[ToolUseUpdate, None]:
    """Run multiple concurrent-safe tools in parallel."""
    import asyncio

    async def run_single(block: Dict[str, Any]) -> List[ToolUseUpdate]:
        results: List[ToolUseUpdate] = []
        async for update in run_tool_use(block, tools, assistant_message_uuid, context):
            results.append(update)
        return results

    tasks = [run_single(block) for block in blocks]
    all_results = await asyncio.gather(*tasks)

    for results in all_results:
        for update in results:
            yield update


async def _run_tools_serially(
    blocks: List[Dict[str, Any]],
    tools: List[Tool],
    assistant_message_uuid: str,
    context: ToolUseContext,
) -> AsyncGenerator[ToolUseUpdate, None]:
    """Run tools one at a time, updating context between each."""
    current_context = context

    for block in blocks:
        async for update in run_tool_use(block, tools, assistant_message_uuid, current_context):
            if update.context_modifier is not None and callable(update.context_modifier):
                current_context = update.context_modifier(current_context)
            yield update
