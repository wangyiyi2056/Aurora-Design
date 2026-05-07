"""Tool Search for Aurora - on-demand tool loading."""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolDefinition:
    """A tool definition with metadata."""
    name: str
    description: str
    parameters: Dict[str, Any]
    type: str = "function"
    loaded: bool = False  # Whether full definition is loaded
    source: Optional[str] = None  # MCP server or skill source
    load_cost: int = 0  # Token cost to load full definition


@dataclass
class ToolSearchResult:
    """Result from tool search."""
    tools: List[ToolDefinition]
    query: str
    total_available: int
    loaded_count: int


class ToolSearchManager:
    """Manages on-demand tool loading following Claude Code patterns.

    Tool definitions are deferred by default:
    - Only tool names consume context at session start
    - Full definitions loaded when tool is actually used
    - Supports MCP tools and Skills
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._name_only_list: List[str] = []  # For initial context

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        source: Optional[str] = None,
        load_cost: int = 0,
    ) -> None:
        """Register a tool definition."""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            source=source,
            load_cost=load_cost,
            loaded=True,  # Registered tools are fully loaded
        )
        self._tools[name] = tool
        self._name_only_list.append(name)

    def register_tool_name_only(
        self,
        name: str,
        source: Optional[str] = None,
    ) -> None:
        """Register only tool name (deferred loading)."""
        tool = ToolDefinition(
            name=name,
            description=f"Tool: {name}",  # Minimal description
            parameters={},
            loaded=False,
            source=source,
        )
        self._tools[name] = tool
        self._name_only_list.append(name)

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> ToolSearchResult:
        """Search for tools matching query."""
        matching: List[ToolDefinition] = []

        query_lower = query.lower()
        for tool in self._tools.values():
            # Match name or description
            if query_lower in tool.name.lower():
                matching.append(tool)
            elif query_lower in tool.description.lower():
                matching.append(tool)

        # Sort by relevance (name match first)
        matching.sort(key=lambda t: (
            0 if query_lower in t.name.lower() else 1,
            t.name,
        ))

        return ToolSearchResult(
            tools=matching[:limit],
            query=query,
            total_available=len(self._tools),
            loaded_count=len([t for t in self._tools.values() if t.loaded]),
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def load_tool(self, name: str) -> Optional[ToolDefinition]:
        """Load full tool definition if deferred."""
        tool = self._tools.get(name)
        if tool and not tool.loaded:
            # Mark as loaded (in real implementation, fetch from source)
            tool.loaded = True
        return tool

    def get_name_only_context(self) -> str:
        """Get minimal context with only tool names."""
        return f"Available tools: {', '.join(self._name_only_list)}"

    def get_full_tools_context(self) -> List[Dict[str, Any]]:
        """Get full tool definitions for LLM tools parameter."""
        tools: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            if tool.loaded:
                tools.append({
                    "type": tool.type,
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                })
        return tools

    def get_all_tool_names(self) -> List[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())

    def estimate_context_cost(self) -> Dict[str, int]:
        """Estimate context token usage."""
        loaded_cost = sum(t.load_cost for t in self._tools.values() if t.loaded)
        name_only_cost = len(self._name_only_list) * 2  # ~2 tokens per name

        return {
            "loaded_tools_cost": loaded_cost,
            "name_only_cost": name_only_cost,
            "total_cost": loaded_cost + name_only_cost,
            "deferred_savings": sum(t.load_cost for t in self._tools.values() if not t.loaded),
        }

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._name_only_list.clear()