"""BashTool — execute shell commands. Ported from Claude-Code's BashTool."""
import asyncio
import os
import shlex
import subprocess
import time
from typing import Any, Dict, List, Optional

from aurora_core.tool.base import (
    Tool,
    ToolCallProgress,
    ToolProgress,
    ToolResult,
    ToolUseContext,
    BashProgress,
    ValidationResult,
    build_tool,
)


TOOL_NAME = "Bash"
TOOL_DESCRIPTION = """Execute shell commands in the project environment.
Use this to run build commands, scripts, tests, or any shell operation.
The command runs in the project root directory.
Output is captured and returned. Long-running commands show progress updates."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute.",
        },
        "description": {
            "type": "string",
            "description": "A short description of what this command does (for display).",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in milliseconds (default: 30000).",
        },
        "workdir": {
            "type": "string",
            "description": "Working directory for the command (default: project root).",
        },
    },
    "required": ["command"],
}

DANGEROUS_COMMANDS = {
    "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777 /",
    "> /dev/sda", "| sh", "| bash",
}

MAX_OUTPUT_CHARS = 50000


async def bash_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress: Optional[ToolCallProgress] = None,
) -> ToolResult[str]:
    """Execute a bash command."""
    command = args.get("command", "")
    timeout = args.get("timeout", 30000) / 1000  # convert to seconds
    workdir = args.get("workdir") or os.getcwd()

    if not command:
        return ToolResult(data="Error: No command provided")

    start = time.time()
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        env=os.environ.copy(),
        shell=True,
    )

    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    truncated = False

    try:
        async def read_stream(stream, storage: List[str], label: str):
            nonlocal truncated
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                # Truncate if output is too large
                total = sum(len(l) for l in storage) + len(decoded)
                if total > MAX_OUTPUT_CHARS and not truncated:
                    storage.append("... [output truncated]")
                    truncated = True
                    break
                storage.append(decoded)

                # Report progress periodically
                if on_progress and len(storage) % 20 == 0:
                    on_progress(ToolProgress(
                        tool_use_id="",
                        data=BashProgress(
                            command=command[:80],
                            stdout=decoded[-200:],
                            elapsed_ms=(time.time() - start) * 1000,
                        ),
                    ))

        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, stdout_lines, "stdout"),
                read_stream(process.stderr, stderr_lines, "stderr"),
            ),
            timeout=timeout,
        )

    except asyncio.TimeoutError:
        process.kill()
        result = "\n".join(stdout_lines[-50:])
        if result:
            result += "\n"
        result += f"\n[Command timed out after {timeout}s]"
        return ToolResult(data=result)

    await process.wait()
    exit_code = process.returncode or 0

    # Build result
    output = ""
    if stdout_lines:
        output += "\n".join(stdout_lines)
    if stderr_lines:
        if output:
            output += "\n"
        output += "\n".join(stderr_lines)

    if exit_code != 0:
        output += f"\n\n[Exit code: {exit_code}]"

    return ToolResult(data=output)


async def bash_validate_input(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    """Validate bash command."""
    command = args.get("command", "")
    if not command:
        return ValidationResult.fail("command is required")

    # Check for dangerous commands
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command:
            return ValidationResult.fail(
                f"Command contains dangerous pattern: {dangerous}",
                error_code=1,
            )

    return ValidationResult.ok()


def bash_is_concurrency_safe(args: Dict[str, Any]) -> bool:
    """Bash commands are NOT concurrency-safe by default."""
    return False


def bash_get_path(args: Dict[str, Any]) -> Optional[str]:
    """Extract a file path from the command if applicable."""
    command = args.get("command", "")
    # Simple heuristic: look for file paths in common commands
    for cmd in ["cat ", "head ", "tail ", "less ", "wc "]:
        if command.startswith(cmd):
            parts = shlex.split(command)
            if len(parts) >= 2:
                return parts[-1]
    return None


def bash_is_destructive(args: Dict[str, Any]) -> bool:
    """Check if the command could be destructive."""
    command = args.get("command", "")
    destructive_patterns = ["rm ", "mv ", "dd ", ">", "|", "mkfs", "chmod"]
    return any(p in command for p in destructive_patterns)


BashTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=bash_call,
    validate_input_fn=bash_validate_input,
    is_concurrency_safe_fn=bash_is_concurrency_safe,
    is_read_only_fn=lambda args: _is_bash_read_only(args.get("command", "")),
    is_destructive_fn=bash_is_destructive,
    get_path_fn=bash_get_path,
    interrupt_behavior="cancel",
    get_activity_description_fn=lambda args: f"Running: {args.get('command', '')[:60]}",
    get_tool_use_summary_fn=lambda args: args.get("description") or args.get("command", "")[:80],
)


def _is_bash_read_only(command: str) -> bool:
    """Heuristic check if a bash command is read-only."""
    read_only_prefixes = [
        "cat ", "ls ", "head ", "tail ", "echo ", "pwd ", "which ",
        "wc ", "sort ", "uniq ", "grep ", "find ", "locate ",
        "npm view ", "pip show ", "python --version", "node --version",
        "npm --version", "git status", "git log", "git diff",
        "git branch", "git remote",
    ]
    return any(command.startswith(cmd) for cmd in read_only_prefixes)
