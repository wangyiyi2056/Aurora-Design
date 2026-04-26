"""Context window monitor for tracking and warning on token usage.

Mirrors Claude-Code's context window tracking:
- Monitors token counts across conversation turns
- Warns when approaching context limits
- Integrates with CostTracker for real-time stats
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from chatbi_core.schema.message import Message


@dataclass
class ContextSnapshot:
    """Snapshot of current context window state."""
    estimated_tokens: int
    max_tokens: int
    usage_percentage: float
    message_count: int
    tool_call_count: int
    timestamp: float = field(default_factory=time.time)

    @property
    def is_warning(self) -> bool:
        return self.usage_percentage >= 80.0

    @property
    def is_critical(self) -> bool:
        return self.usage_percentage >= 90.0

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.estimated_tokens)


class ContextMonitor:
    """Monitors context window usage across conversation turns.

    Usage::

        monitor = ContextMonitor(max_tokens=200000)
        snap = monitor.snapshot(messages)
        if snap.is_critical:
            print("Context window nearly full, compacting...")
    """

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self._warnings_issued: int = 0
        self._last_warning_time: float = 0
        self._history: List[ContextSnapshot] = []

    def estimate_tokens(self, messages: List[Message]) -> int:
        """Estimate token count for messages.

        Uses a simple char-based heuristic (~4 chars/token for English text).
        """
        total_chars = 0
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total_chars += len(json.dumps(part))
                    else:
                        total_chars += len(str(part))

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total_chars += len(json.dumps(tc.function))

            if msg.tool_call_id:
                total_chars += len(msg.tool_call_id)
            if msg.name:
                total_chars += len(msg.name)

        # ~4 chars per token for English text
        return total_chars // 4

    def snapshot(self, messages: List[Message]) -> ContextSnapshot:
        """Take a context window snapshot."""
        tokens = self.estimate_tokens(messages)
        tool_calls = sum(1 for m in messages if m.tool_calls)
        snap = ContextSnapshot(
            estimated_tokens=tokens,
            max_tokens=self.max_tokens,
            usage_percentage=round(tokens / self.max_tokens * 100, 1) if self.max_tokens > 0 else 0,
            message_count=len(messages),
            tool_call_count=tool_calls,
        )
        self._history.append(snap)
        # Keep last 100 snapshots
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return snap

    def check(self, messages: List[Message]) -> Tuple[bool, Optional[str]]:
        """Check if context needs attention.

        Returns:
            (needs_action, warning_message) tuple
        """
        snap = self.snapshot(messages)

        if snap.is_critical:
            self._warnings_issued += 1
            self._last_warning_time = time.time()
            return True, (
                f"Context window {snap.usage_percentage:.0f}% full "
                f"({snap.estimated_tokens}/{snap.max_tokens} tokens). "
                f"Compaction recommended."
            )

        if snap.is_warning:
            self._warnings_issued += 1
            self._last_warning_time = time.time()
            return False, (
                f"Context window {snap.usage_percentage:.0f}% full. "
                f"Monitor usage."
            )

        return False, None

    def should_compact(self, messages: List[Message], threshold: float = 0.9) -> bool:
        """Check if compaction should be triggered."""
        tokens = self.estimate_tokens(messages)
        return tokens >= self.max_tokens * threshold

    def get_growth_rate(self) -> float:
        """Estimate token growth rate (tokens per turn) from history."""
        if len(self._history) < 2:
            return 0.0
        recent = self._history[-5:]
        if len(recent) < 2:
            return 0.0
        first, last = recent[0], recent[-1]
        elapsed = last.timestamp - first.timestamp
        if elapsed <= 0:
            return 0.0
        return (last.estimated_tokens - first.estimated_tokens) / elapsed

    def predict_full(self, messages: List[Message]) -> Optional[int]:
        """Predict turns until context is full. Returns None if stable."""
        rate = self.get_growth_rate()
        if rate <= 0:
            return None
        current = self.estimate_tokens(messages)
        remaining = self.max_tokens - current
        return int(remaining / rate) if rate > 0 else None

    def get_history(self) -> List[dict]:
        """Get snapshot history for analysis."""
        return [
            {
                "tokens": s.estimated_tokens,
                "percentage": s.usage_percentage,
                "messages": s.message_count,
                "timestamp": s.timestamp,
            }
            for s in self._history
        ]

    def reset(self) -> None:
        """Reset monitoring state."""
        self._warnings_issued = 0
        self._last_warning_time = 0
        self._history.clear()
