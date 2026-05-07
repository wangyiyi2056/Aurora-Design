"""StreamingToolExecutor — concurrent-safe tool execution with progress.

Ported from Claude-Code's StreamingToolExecutor.ts.

Manages the lifecycle of multiple tool calls:
- Concurrent-safe tools execute in parallel
- Non-concurrent tools execute serially (exclusive access)
- Results are buffered and yielded in order
- Sibling errors cancel concurrent bash commands
- Progress messages are yielded immediately
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Set

from aurora_core.tool.base import (
    Tool,
    ToolProgress,
    ToolProgressData,
    ToolUseContext,
    find_tool_by_name,
)
from aurora_core.tool.executor import ToolUseUpdate, run_tool_use


@dataclass
class MessageUpdate:
    """A yielded update from the executor."""
    message: Optional[Dict[str, Any]] = None
    new_context: Optional[ToolUseContext] = None


class StreamingToolExecutor:
    """Executes tools as they arrive with concurrency control.

    - Concurrent-safe tools → parallel execution
    - Non-concurrent tools → exclusive/serial execution
    - Results yielded in tool-received order
    """

    def __init__(
        self,
        tool_definitions: List[Tool],
        tool_use_context: ToolUseContext,
    ):
        self._tool_definitions = tool_definitions
        self._context = tool_use_context
        self._tools: List[TrackedTool] = []
        self._has_errored = False
        self._errored_tool_description = ""
        self._discarded = False

    def add_tool(self, block: Dict[str, Any], assistant_message_uuid: str) -> None:
        """Queue a tool for execution. Starts immediately if concurrency allows."""
        tool_def = find_tool_by_name(self._tool_definitions, block.get("name", ""))
        if not tool_def:
            self._tools.append(TrackedTool(
                id=block.get("id", ""),
                block=block,
                assistant_message_uuid=assistant_message_uuid,
                status="completed",
                is_concurrency_safe=True,
            ))
            return

        is_concurrency_safe = False
        try:
            is_concurrency_safe = tool_def.is_concurrency_safe(
                block.get("input", {})
            )
        except Exception:
            pass

        self._tools.append(TrackedTool(
            id=block.get("id", ""),
            block=block,
            assistant_message_uuid=assistant_message_uuid,
            status="queued",
            is_concurrency_safe=is_concurrency_safe,
        ))

    async def run(self) -> AsyncGenerator[MessageUpdate, None]:
        """Run all queued tools and yield results as they complete."""
        if self._discarded:
            return

        # Start all tools respecting concurrency constraints
        self._schedule_tools()

        # Yield results as they become available
        while self._has_unfinished_tools():
            for result in self._get_completed_results():
                yield result

            if self._has_executing_tools() and not self._has_completed_results():
                # Wait for any tool to complete
                executing = [t for t in self._tools if t.status == "executing" and t._promise]
                if executing:
                    done, _ = await asyncio.wait(
                        [t._promise for t in executing],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    await asyncio.gather(*done, return_exceptions=True)

        for result in self._get_completed_results():
            yield result

    def discard(self) -> None:
        """Discard all pending/in-progress tools."""
        self._discarded = True

    def get_updated_context(self) -> ToolUseContext:
        return self._context

    # ── Internal ────────────────────────────────────────────────

    def _schedule_tools(self) -> None:
        """Start executing tools respecting concurrency semantics."""
        started = set()
        changed = True
        while changed:
            changed = False
            for i, tool in enumerate(self._tools):
                if tool.status != "queued" or i in started:
                    continue
                if self._can_execute_tool(tool.is_concurrency_safe):
                    started.add(i)
                    changed = True
                    # Schedule execution
                    asyncio.ensure_future(self._execute_tool(tool))
                elif not tool.is_concurrency_safe:
                    break  # Non-concurrent tool blocks subsequent queued tools

    def _can_execute_tool(self, is_concurrency_safe: bool) -> bool:
        executing = [t for t in self._tools if t.status == "executing"]
        if not executing:
            return True
        if is_concurrency_safe:
            return all(t.is_concurrency_safe for t in executing)
        return False

    async def _execute_tool(self, tool: "TrackedTool") -> None:
        tool.status = "executing"

        async def collect_results() -> None:
            generator = run_tool_use(
                tool.block,
                self._tool_definitions,
                assistant_message_uuid=tool.assistant_message_uuid,
                context=self._context,
            )

            messages: List[Dict[str, Any]] = []
            this_tool_errored = False

            async for update in generator:
                if update.message:
                    msg_type = update.message.get("type", "")
                    if msg_type == "progress":
                        tool.pending_progress.append(update.message)
                    else:
                        messages.append(update.message)

                    # Track errors
                    is_error = False
                    if update.message.get("role") == "user":
                        content = update.message.get("content", [])
                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get("is_error"):
                                    is_error = True
                                    break

                    if is_error:
                        this_tool_errored = True
                        tool_name = tool.block.get("name", "")
                        if tool_name == "Bash":
                            self._has_errored = True
                            desc = self._get_tool_description(tool)
                            self._errored_tool_description = desc

            tool.results = messages
            tool.status = "completed"

        tool._promise = asyncio.ensure_future(collect_results())

    def _get_tool_description(self, tool: "TrackedTool") -> str:
        inp = tool.block.get("input", {})
        summary = inp.get("command") or inp.get("file_path") or inp.get("pattern") or ""
        if isinstance(summary, str) and summary:
            truncated = summary[:40] + "…" if len(summary) > 40 else summary
            return f"{tool.block.get('name', '')}({truncated})"
        return tool.block.get("name", "")

    def _get_completed_results(self) -> Generator[MessageUpdate, None, None]:
        if self._discarded:
            return

        for tool in self._tools:
            # Yield pending progress immediately
            while tool.pending_progress:
                msg = tool.pending_progress.pop(0)
                yield MessageUpdate(message=msg, new_context=self._context)

            if tool.status == "yielded":
                continue

            if tool.status == "completed" and tool.results is not None:
                tool.status = "yielded"
                for msg in tool.results:
                    yield MessageUpdate(message=msg, new_context=self._context)

            elif tool.status == "executing" and not tool.is_concurrency_safe:
                break

    def _has_unfinished_tools(self) -> bool:
        return any(t.status != "yielded" for t in self._tools)

    def _has_executing_tools(self) -> bool:
        return any(t.status == "executing" for t in self._tools)

    def _has_completed_results(self) -> bool:
        return any(t.status == "completed" for t in self._tools)


@dataclass
class TrackedTool:
    """Internal tool execution tracking state."""
    id: str
    block: Dict[str, Any]
    assistant_message_uuid: str
    status: str  # queued | executing | completed | yielded
    is_concurrency_safe: bool
    pending_progress: List[Dict[str, Any]] = field(default_factory=list)
    results: Optional[List[Dict[str, Any]]] = None
    _promise: Any = None
