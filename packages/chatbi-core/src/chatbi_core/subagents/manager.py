"""Subagent Manager for ChatBI - manages subagent execution."""

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbi_core.subagents.definition import SubagentDefinition


@dataclass
class SubagentResult:
    """Result from subagent execution."""
    subagent_name: str
    success: bool
    summary: str
    messages_processed: int = 0
    tools_used: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    error: Optional[str] = None
    parent_tool_use_id: Optional[str] = None


class SubagentManager:
    """Manages subagent creation and execution.

    Subagents:
    - Get their own fresh context
    - Work independently without bloating main context
    - Return summary when done
    - Can run in parallel
    """

    def __init__(
        self,
        agents_path: Optional[str] = None,
        global_agents_path: Optional[str] = None,
    ):
        self.agents_path = Path(agents_path or ".chatbi/agents")
        self.global_agents_path = Path(
            global_agents_path or os.path.expanduser("~/.chatbi/agents")
        )

        self._definitions: Dict[str, SubagentDefinition] = {}
        self._load_definitions()

    def _load_definitions(self) -> None:
        """Load subagent definitions from Markdown files."""
        # Load global agents
        if self.global_agents_path.exists():
            for md_file in self.global_agents_path.glob("*.md"):
                try:
                    content = md_file.read_text()
                    definition = SubagentDefinition.from_markdown(content)
                    self._definitions[definition.name] = definition
                except Exception:
                    continue

        # Load project agents (override global)
        if self.agents_path.exists():
            for md_file in self.agents_path.glob("*.md"):
                try:
                    content = md_file.read_text()
                    definition = SubagentDefinition.from_markdown(content)
                    self._definitions[definition.name] = definition
                except Exception:
                    continue

    def register(self, definition: SubagentDefinition) -> None:
        """Register a subagent definition."""
        self._definitions[definition.name] = definition

    def get(self, name: str) -> Optional[SubagentDefinition]:
        """Get a subagent definition by name."""
        return self._definitions.get(name)

    def list_subagents(self) -> List[Dict[str, Any]]:
        """List all available subagents."""
        return [d.to_dict() for d in self._definitions.values()]

    async def execute(
        self,
        name: str,
        task: str,
        llm_client: Any,  # LLM client with achat method
        skill_registry: Any = None,  # Optional skill registry
        parent_tool_use_id: Optional[str] = None,
    ) -> SubagentResult:
        """Execute a subagent with its own context."""
        definition = self._definitions.get(name)
        if not definition:
            return SubagentResult(
                subagent_name=name,
                success=False,
                summary=f"Subagent '{name}' not found",
                error="Subagent not found",
            )

        start_time = time.time()

        try:
            # Create isolated context with subagent prompt
            messages = [
                {"role": "system", "content": definition.prompt},
                {"role": "user", "content": task},
            ]

            # Get allowed tools
            tools = None
            if skill_registry and definition.tools:
                # Build tools from allowed list
                tools = []
                for tool_name in definition.tools:
                    if tool_name == "Agent":
                        continue  # Subagents shouldn't spawn more agents
                    try:
                        skill = skill_registry.get(tool_name)
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": skill.name,
                                "description": skill.description,
                                "parameters": skill.parameters,
                            },
                        })
                    except KeyError:
                        continue

            # Execute with timeout
            max_rounds = 3
            tools_used: List[str] = []
            messages_processed = 0

            async def execute_with_timeout():
                for _ in range(max_rounds):
                    output = await llm_client.achat(
                        messages,
                        tools=tools,
                        tool_choice="auto",
                    )
                    messages_processed += 1

                    if output.finish_reason == "tool_calls" and output.tool_calls:
                        # Record tools used
                        for tc in output.tool_calls:
                            fn_name = tc.function.get("name", "")
                            if fn_name not in tools_used:
                                tools_used.append(fn_name)

                        # Execute tools and append results
                        messages.append({
                            "role": "assistant",
                            "content": output.text,
                            "tool_calls": [
                                {"id": tc.id, "type": tc.type, "function": tc.function}
                                for tc in output.tool_calls
                            ],
                        })

                        for tc in output.tool_calls:
                            fn_name = tc.function.get("name", "")
                            fn_args = tc.function.get("arguments", "{}")
                            try:
                                skill = skill_registry.get(fn_name)
                                import json
                                args = json.loads(fn_args) if fn_args else {}
                                result = await skill.execute(**args)
                            except Exception as e:
                                result = f"Error: {e}"
                            messages.append({
                                "role": "tool",
                                "content": str(result),
                                "tool_call_id": tc.id,
                                "name": fn_name,
                            })
                        continue

                    # Final answer
                    return output.text

                return "Maximum rounds reached"

            # Run with timeout
            summary = await asyncio.wait_for(
                execute_with_timeout(),
                timeout=definition.timeout_seconds,
            )

            return SubagentResult(
                subagent_name=name,
                success=True,
                summary=summary,
                messages_processed=messages_processed,
                tools_used=tools_used,
                execution_time=time.time() - start_time,
                parent_tool_use_id=parent_tool_use_id,
            )

        except asyncio.TimeoutError:
            return SubagentResult(
                subagent_name=name,
                success=False,
                summary="Subagent execution timed out",
                error="Timeout",
                execution_time=definition.timeout_seconds,
                parent_tool_use_id=parent_tool_use_id,
            )
        except Exception as e:
            return SubagentResult(
                subagent_name=name,
                success=False,
                summary=f"Subagent error: {e}",
                error=str(e),
                execution_time=time.time() - start_time,
                parent_tool_use_id=parent_tool_use_id,
            )

    async def execute_parallel(
        self,
        tasks: List[Dict[str, str]],  # [{"name": "...", "task": "..."}, ...]
        llm_client: Any,
        skill_registry: Any = None,
    ) -> List[SubagentResult]:
        """Execute multiple subagents in parallel."""
        results = await asyncio.gather(
            *[
                self.execute(
                    name=t["name"],
                    task=t["task"],
                    llm_client=llm_client,
                    skill_registry=skill_registry,
                )
                for t in tasks
            ]
        )
        return list(results)

    def save_definition(self, definition: SubagentDefinition) -> str:
        """Save a subagent definition to Markdown file."""
        # Save to project path by default
        if not self.agents_path.exists():
            self.agents_path.mkdir(parents=True, exist_ok=True)

        file_path = self.agents_path / f"{definition.name}.md"
        file_path.write_text(definition.to_markdown())

        # Register in memory
        self._definitions[definition.name] = definition
        return str(file_path)