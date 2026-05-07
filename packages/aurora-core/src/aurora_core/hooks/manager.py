"""Hooks Manager for Aurora - manages lifecycle hooks."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from aurora_core.hooks.schema import Hook, HookType, HookMatcher, HookResult


class HookManager:
    """Manages hook execution following Claude Code patterns.

    Hooks can be:
    - Shell commands (run via subprocess)
    - Python functions (called directly)

    Configuration is loaded from:
    - ~/.aurora/settings.json (global)
    - .aurora/settings.json (project)
    """

    def __init__(
        self,
        global_settings_path: Optional[str] = None,
        project_settings_path: Optional[str] = None,
    ):
        self.global_settings_path = Path(
            global_settings_path or os.path.expanduser("~/.aurora/settings.json")
        )
        self.project_settings_path = Path(project_settings_path) if project_settings_path else None

        self._hooks: Dict[HookType, List[Hook]] = {}
        self._load_hooks()

    def _load_hooks(self) -> None:
        """Load hooks from settings files."""
        # Default empty hooks for each type
        for hook_type in HookType:
            self._hooks[hook_type] = []

        # Load global settings
        if self.global_settings_path.exists():
            self._load_settings_file(self.global_settings_path)

        # Load project settings (override global)
        if self.project_settings_path and self.project_settings_path.exists() and self.project_settings_path.is_file():
            self._load_settings_file(self.project_settings_path)

    def _load_settings_file(self, path: Path) -> None:
        """Load hooks from a settings JSON file."""
        try:
            settings = json.loads(path.read_text())
            hooks_config = settings.get("hooks", {})

            for hook_type_str, hook_entries in hooks_config.items():
                try:
                    hook_type = HookType(hook_type_str)
                except ValueError:
                    continue

                for entry in hook_entries:
                    matcher = entry.get("matcher", "*")
                    hooks_list = entry.get("hooks", [])
                    description = entry.get("description")
                    enabled = entry.get("enabled", True)

                    # Convert hooks list to proper format
                    processed_hooks: List[Union[Callable, str]] = []
                    for h in hooks_list:
                        if isinstance(h, str):
                            processed_hooks.append(h)
                        elif callable(h):
                            processed_hooks.append(h)

                    hook = Hook(
                        type=hook_type,
                        matchers=[HookMatcher(matcher=matcher, hooks=processed_hooks)],
                        description=description,
                        enabled=enabled,
                    )
                    self._hooks[hook_type].append(hook)
        except (json.JSONDecodeError, KeyError) as e:
            # Log error but don't crash
            pass

    def register_hook(
        self,
        hook_type: HookType,
        matcher: str,
        hook: Union[Callable, str],
        description: Optional[str] = None,
    ) -> None:
        """Register a new hook."""
        existing_matcher = None
        for h in self._hooks[hook_type]:
            for m in h.matchers:
                if m.matcher == matcher:
                    existing_matcher = m
                    break

        if existing_matcher:
            existing_matcher.hooks.append(hook)
        else:
            new_hook = Hook(
                type=hook_type,
                matchers=[HookMatcher(matcher=matcher, hooks=[hook])],
                description=description,
            )
            self._hooks[hook_type].append(new_hook)

    def _execute_shell_hook(
        self,
        command: str,
        input_data: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> HookResult:
        """Execute a shell command hook."""
        try:
            # Replace $FILE_PATH if present
            if file_path and "$FILE_PATH" in command:
                command = command.replace("$FILE_PATH", file_path)

            # Run the command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
            )

            if result.returncode == 2:  # Blocked signal
                return HookResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr,
                    blocked=True,
                )

            return HookResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )
        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                error="Hook execution timed out",
            )
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
            )

    async def _execute_python_hook(
        self,
        func: Callable,
        input_data: Optional[Dict[str, Any]] = None,
        tool_use_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> HookResult:
        """Execute a Python function hook."""
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(input_data, tool_use_id, context)
            else:
                result = func(input_data, tool_use_id, context)

            if result is None:
                return HookResult(success=True)
            if isinstance(result, dict):
                return HookResult(
                    success=True,
                    modified_input=result,
                )
            if isinstance(result, HookResult):
                return result
            return HookResult(success=True, output=str(result))
        except Exception as e:
            return HookResult(
                success=False,
                error=str(e),
            )

    async def execute_hooks(
        self,
        hook_type: HookType,
        tool_name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        tool_use_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> List[HookResult]:
        """Execute all matching hooks for a given type."""
        results: List[HookResult] = []

        hooks = self._hooks.get(hook_type, [])
        for hook in hooks:
            matching = hook.get_matching_hooks(tool_name)
            for h in matching:
                if isinstance(h, str):
                    # Shell command
                    result = self._execute_shell_hook(h, input_data, file_path)
                else:
                    # Python function
                    result = await self._execute_python_hook(
                        h, input_data, tool_use_id, context
                    )
                results.append(result)

                # If blocked, stop executing
                if result.blocked:
                    break

        return results

    async def run_pre_tool_use(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        file_path: Optional[str] = None,
    ) -> HookResult:
        """Run PreToolUse hooks and return combined result."""
        results = await self.execute_hooks(
            HookType.PRE_TOOL_USE,
            tool_name=tool_name,
            input_data=input_data,
            file_path=file_path,
        )

        # Check if any blocked
        for r in results:
            if r.blocked:
                return r

        # Combine modified inputs
        modified: Dict[str, Any] = {}
        for r in results:
            if r.modified_input:
                modified.update(r.modified_input)

        if modified:
            return HookResult(success=True, modified_input=modified)

        # Return first error if any
        for r in results:
            if not r.success:
                return r

        return HookResult(success=True)

    async def run_post_tool_use(
        self,
        tool_name: str,
        output_data: Any,
        file_path: Optional[str] = None,
    ) -> HookResult:
        """Run PostToolUse hooks."""
        results = await self.execute_hooks(
            HookType.POST_TOOL_USE,
            tool_name=tool_name,
            input_data={"output": output_data},
            file_path=file_path,
        )

        # Return first error if any
        for r in results:
            if not r.success:
                return r

        return HookResult(success=True)

    async def run_session_start(self) -> List[HookResult]:
        """Run SessionStart hooks."""
        return await self.execute_hooks(HookType.SESSION_START)

    async def run_session_end(self) -> List[HookResult]:
        """Run SessionEnd hooks."""
        return await self.execute_hooks(HookType.SESSION_END)

    async def run_stop(self) -> List[HookResult]:
        """Run Stop hooks."""
        return await self.execute_hooks(HookType.STOP)

    def get_hooks(self, hook_type: HookType) -> List[Hook]:
        """Get all hooks for a type."""
        return self._hooks.get(hook_type, [])

    def clear_hooks(self, hook_type: Optional[HookType] = None) -> None:
        """Clear hooks for a type or all hooks."""
        if hook_type:
            self._hooks[hook_type] = []
        else:
            for ht in HookType:
                self._hooks[ht] = []