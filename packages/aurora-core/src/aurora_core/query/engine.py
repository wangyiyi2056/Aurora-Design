"""Query engine for model routing and tool selection.

Mirrors Claude-Code's query execution pipeline:
- Model routing based on task complexity
- Tool filtering by relevance and permission
- Response processing with tool call handling
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from aurora_core.schema.message import Message, ModelOutput


class TaskComplexity(str, Enum):
    SIMPLE = "simple"       # Single query, no tools needed
    MODERATE = "moderate"   # May need tools, 1-3 rounds
    COMPLEX = "complex"     # Multi-step, many tools
    AGENT = "agent"         # Requires agent delegation


@dataclass
class QueryConfig:
    """Configuration for query execution."""
    max_tool_rounds: int = 5
    tool_choice: str = "auto"
    temperature: float = 0.0
    max_tokens: int = 4096

    # Tool filtering
    min_confidence_for_tool: float = 0.3
    max_tools_per_query: int = 20

    # Model routing
    prefer_cheap_model: bool = True


class QueryEngine:
    """Executes queries with intelligent model routing and tool selection.

    Usage::

        engine = QueryEngine(llm, tools, config=QueryConfig())
        output = await engine.execute(messages)
    """

    def __init__(
        self,
        llm,
        tools: Optional[List[Any]] = None,
        config: Optional[QueryConfig] = None,
        cost_tracker=None,
    ):
        self.llm = llm
        self.tools = tools or []
        self.config = config or QueryConfig()
        self.cost_tracker = cost_tracker

        # Per-query state
        self._round_count: int = 0
        self._tool_call_history: List[Dict] = []

    def classify_complexity(self, messages: List[Message]) -> TaskComplexity:
        """Classify task complexity to route to appropriate model.

        Heuristics:
        - SIMPLE: Short query, no code/tool mentions
        - MODERATE: Standard query, may reference data/files
        - COMPLEX: Long query with multi-step instructions
        - AGENT: Explicit sub-agent or complex multi-step
        """
        user_text = ""
        for m in messages:
            if m.role == "user":
                content = m.content
                if isinstance(content, str):
                    user_text += content + " "
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            user_text += part.get("text", "") + " "

        user_text = user_text.strip().lower()
        word_count = len(user_text.split())

        # Agent keywords
        agent_keywords = ["subagent", "delegate", "multi-agent", "parallel"]
        if any(kw in user_text for kw in agent_keywords):
            return TaskComplexity.AGENT

        # Complex: long or multi-step
        if word_count > 200:
            return TaskComplexity.COMPLEX
        multi_step_markers = ["first", "then", "finally", "step 1", "step 2"]
        if sum(1 for m in multi_step_markers if m in user_text) >= 2:
            return TaskComplexity.COMPLEX

        # Simple: short greeting or simple question
        if word_count < 10:
            return TaskComplexity.SIMPLE

        return TaskComplexity.MODERATE

    def filter_tools(self, messages: List[Message]) -> List[Any]:
        """Filter tools by relevance to the query.

        Returns the most relevant tools, respecting max_tools_per_query.
        """
        if not self.tools:
            return []

        user_text = ""
        for m in messages:
            if m.role == "user":
                content = m.content
                if isinstance(content, str):
                    user_text += content + " "
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            user_text += part.get("text", "") + " "

        user_text = user_text.lower()

        # Score each tool by keyword relevance
        scored: List[Tuple[float, Any]] = []
        for tool in self.tools:
            name = getattr(tool, "name", "")
            desc = getattr(tool, "description", "")
            score = self._relevance_score(user_text, name, desc)
            scored.append((score, tool))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [t for _, t in scored[:self.config.max_tools_per_query]]

        return selected

    def _relevance_score(self, query: str, name: str, description: str) -> float:
        """Score tool relevance to query."""
        score = 0.0
        name_lower = name.lower()
        desc_lower = description.lower()

        # Name is a strong signal
        if name_lower in query:
            score += 0.5

        # Keyword overlap
        name_words = set(name_lower.replace("_", " ").replace("-", " ").split())
        desc_words = set(desc_lower.split())
        query_words = set(query.split())

        name_overlap = len(name_words & query_words)
        desc_overlap = len(desc_words & query_words)

        score += min(name_overlap * 0.1, 0.3)
        score += min(desc_overlap * 0.02, 0.2)

        return score

    def select_model(self, messages: List[Message]) -> str:
        """Select the best model based on task complexity."""
        complexity = self.classify_complexity(messages)

        model_name = getattr(self.llm.config, "model_name", "default")

        # Route based on complexity
        if complexity == TaskComplexity.SIMPLE:
            # Prefer cheaper/faster model if available
            return model_name  # Would route to haiku if available
        elif complexity == TaskComplexity.COMPLEX or complexity == TaskComplexity.AGENT:
            # Prefer most capable model
            return model_name  # Would route to opus if available

        return model_name

    def build_tool_param(self, messages: List[Message]) -> Optional[List[Dict]]:
        """Build the tools parameter for the LLM API call."""
        filtered = self.filter_tools(messages)
        if not filtered:
            return None

        result = []
        for t in filtered:
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": getattr(t, "input_schema", {}),
                },
            })
        return result

    async def execute(
        self,
        messages: List[Message],
    ) -> Tuple[ModelOutput, List[Dict]]:
        """Execute a query with tool call handling.

        Returns:
            (final_output, tool_call_history) tuple
        """
        tools = self.build_tool_param(messages)

        output = await self.llm.achat(
            messages,
            tools=tools,
            tool_choice=self.config.tool_choice,
        )

        # Track usage
        if self.cost_tracker and output.usage:
            self.cost_tracker.record_usage(
                model_name=getattr(self.llm.config, "model_name", ""),
                input_tokens=output.usage.get("input_tokens", 0),
                output_tokens=output.usage.get("output_tokens", 0),
            )

        tool_calls_data = []
        if output.tool_calls:
            for tc in output.tool_calls:
                tool_calls_data.append({
                    "id": tc.id,
                    "name": tc.function.get("name", "") if tc.function else "",
                    "input": tc.function.get("arguments", "{}") if tc.function else "{}",
                })

        return output, tool_calls_data

    def record_tool_result(self, tool_name: str, result: str, success: bool) -> None:
        """Record tool execution result."""
        self._round_count += 1
        self._tool_call_history.append({
            "name": tool_name,
            "success": success,
            "timestamp": time.time(),
        })
        if self.cost_tracker:
            self.cost_tracker.record_tool_call(success=success)

    @property
    def rounds(self) -> int:
        return self._round_count

    def reset(self) -> None:
        """Reset per-query state."""
        self._round_count = 0
        self._tool_call_history.clear()
