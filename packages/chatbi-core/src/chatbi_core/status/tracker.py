"""Usage and cost tracker for session statistics.

Mirrors Claude-Code's:
- cost-tracker.ts: Cost accumulation, session persistence
- bootstrap/state.ts: Global STATE with session stat fields
- utils/tokens.ts: Token extraction from API responses
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

from chatbi_core.status.models import (
    CostStats,
    CurrentUsage,
    ContextWindow,
    MemoryStats,
    ToolStats,
)


# Pricing tiers (USD per 1M tokens)
DEFAULT_PRICING = {
    "input": 3.00,
    "output": 15.00,
    "cache_write": 3.75,
    "cache_read": 0.30,
}

MODEL_PRICING: Dict[str, dict] = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache_write": 2.50, "cache_read": 0.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_write": 0.15, "cache_read": 0.075},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "cache_write": 10.00, "cache_read": 2.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08},
}


@dataclass
class ModelUsage:
    """Per-model accumulated usage."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float = 0.0


class CostTracker:
    """Tracks session cost, token usage, and performance metrics.

    Usage::

        tracker = CostTracker()
        tracker.record_usage(
            model_name="gpt-4o",
            input_tokens=1500,
            output_tokens=500,
            api_duration_ms=1200,
        )
        stats = tracker.get_stats()
    """

    def __init__(self):
        self._lock = Lock()

        # Accumulated totals
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cache_read_tokens: int = 0
        self.total_cache_creation_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.total_api_duration_ms: int = 0
        self.total_tool_duration_ms: int = 0
        self.total_lines_added: int = 0
        self.total_lines_removed: int = 0
        self.total_tool_calls: int = 0
        self.successful_tool_calls: int = 0
        self.failed_tool_calls: int = 0

        # Session timing
        self.start_time: float = time.time()
        self.last_interaction_time: float = time.time()

        # Per-model tracking
        self.model_usage: Dict[str, ModelUsage] = {}

        # Latest API response usage
        self._latest_usage: Optional[CurrentUsage] = None

    def record_usage(
        self,
        model_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        api_duration_ms: int = 0,
    ) -> None:
        """Record token usage from an API response."""
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cache_read_tokens += cache_read_input_tokens
            self.total_cache_creation_tokens += cache_creation_input_tokens
            self.total_api_duration_ms += api_duration_ms

            # Compute cost
            pricing = MODEL_PRICING.get(model_name, DEFAULT_PRICING)
            cost = (
                (input_tokens / 1_000_000) * pricing["input"]
                + (output_tokens / 1_000_000) * pricing["output"]
                + (cache_read_input_tokens / 1_000_000) * pricing["cache_read"]
                + (cache_creation_input_tokens / 1_000_000) * pricing["cache_write"]
            )
            self.total_cost_usd += cost

            # Per-model tracking
            if model_name:
                if model_name not in self.model_usage:
                    self.model_usage[model_name] = ModelUsage()
                mu = self.model_usage[model_name]
                mu.input_tokens += input_tokens
                mu.output_tokens += output_tokens
                mu.cache_read_input_tokens += cache_read_input_tokens
                mu.cache_creation_input_tokens += cache_creation_input_tokens
                mu.cost_usd += cost

            # Latest usage snapshot
            self._latest_usage = CurrentUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
            )

            self.last_interaction_time = time.time()

    def record_tool_call(self, success: bool, duration_ms: int = 0) -> None:
        """Record a tool execution."""
        with self._lock:
            self.total_tool_calls += 1
            if success:
                self.successful_tool_calls += 1
            else:
                self.failed_tool_calls += 1
            self.total_tool_duration_ms += duration_ms
            self.last_interaction_time = time.time()

    def record_lines_changed(self, added: int, removed: int) -> None:
        """Record lines added/removed by edit tools."""
        with self._lock:
            self.total_lines_added += added
            self.total_lines_removed += removed

    def get_current_usage(self) -> CurrentUsage:
        """Get latest API response usage."""
        with self._lock:
            if self._latest_usage:
                return self._latest_usage
            return CurrentUsage()

    def get_cost_stats(self) -> CostStats:
        """Get accumulated cost statistics."""
        with self._lock:
            return CostStats(
                total_cost_usd=round(self.total_cost_usd, 4),
                total_duration_ms=int((time.time() - self.start_time) * 1000),
                total_api_duration_ms=self.total_api_duration_ms,
                total_tool_duration_ms=self.total_tool_duration_ms,
                total_lines_added=self.total_lines_added,
                total_lines_removed=self.total_lines_removed,
            )

    def get_context_window(self, context_window_size: int = 200000) -> ContextWindow:
        """Get context window usage."""
        with self._lock:
            return ContextWindow(
                total_input_tokens=self.total_input_tokens,
                total_output_tokens=self.total_output_tokens,
                context_window_size=context_window_size,
                cache_creation_input_tokens=self.total_cache_creation_tokens,
                cache_read_input_tokens=self.total_cache_read_tokens,
            )

    def get_tool_stats(self, active_tool_count: int = 0) -> ToolStats:
        """Get tool execution statistics."""
        with self._lock:
            return ToolStats(
                total_tool_calls=self.total_tool_calls,
                successful_calls=self.successful_tool_calls,
                failed_calls=self.failed_tool_calls,
                active_tool_count=active_tool_count,
            )

    def get_memory_stats(self, memory_manager=None) -> MemoryStats:
        """Get memory system statistics."""
        stats = MemoryStats()
        if memory_manager:
            try:
                entries = memory_manager.list_entries()
                stats.total_entries = len(entries)
                stats.user_memories = sum(1 for e in entries if getattr(e, "type", "") == "user")
                stats.project_memories = sum(1 for e in entries if getattr(e, "type", "") == "project")
                stats.feedback_entries = sum(1 for e in entries if getattr(e, "type", "") == "feedback")
            except Exception:
                pass
        return stats

    def get_stats(self) -> dict:
        """Get all accumulated statistics as a dictionary."""
        return {
            "cost": self.get_cost_stats(),
            "context_window": self.get_context_window(),
            "current_usage": self.get_current_usage(),
            "tools": self.get_tool_stats(),
            "model_usage": {
                name: {
                    "input_tokens": mu.input_tokens,
                    "output_tokens": mu.output_tokens,
                    "cache_read_input_tokens": mu.cache_read_input_tokens,
                    "cache_creation_input_tokens": mu.cache_creation_input_tokens,
                    "cost_usd": round(mu.cost_usd, 4),
                }
                for name, mu in self.model_usage.items()
            },
        }

    def reset(self) -> None:
        """Reset all tracking state."""
        with self._lock:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_cache_read_tokens = 0
            self.total_cache_creation_tokens = 0
            self.total_cost_usd = 0.0
            self.total_api_duration_ms = 0
            self.total_tool_duration_ms = 0
            self.total_lines_added = 0
            self.total_lines_removed = 0
            self.total_tool_calls = 0
            self.successful_tool_calls = 0
            self.failed_tool_calls = 0
            self.start_time = time.time()
            self.last_interaction_time = time.time()
            self.model_usage.clear()
            self._latest_usage = None
