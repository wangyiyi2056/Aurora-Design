"""Context Compaction for Aurora - manages context window limits."""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from aurora_core.schema.message import Message


@dataclass
class CompactionConfig:
    """Configuration for context compaction."""
    max_tokens: int = 200000  # Default context window
    warning_threshold: float = 0.8  # Warn at 80%
    compact_threshold: float = 0.9  # Compact at 90%
    preserve_recent_messages: int = 10  # Keep last N messages
    preserve_user_requests: bool = True  # Keep user requests
    preserve_code_snippets: bool = True  # Keep key code snippets


@dataclass
class ContextSummary:
    """Summary of compacted context."""
    original_messages: int
    compacted_messages: int
    preserved_messages: int
    summary_text: Optional[str] = None
    compaction_ratio: float = 0.0


class ContextCompactor:
    """Manages context compaction following Claude Code patterns.

    Compaction strategy:
    1. Clear older tool outputs first
    2. Summarize conversation if needed
    3. Preserve user requests and key code snippets
    4. Stop auto-compaction if thrashing (single large file)
    """

    def __init__(self, config: Optional[CompactionConfig] = None):
        self.config = config or CompactionConfig()
        self._compaction_count: int = 0
        self._last_compaction_time: float = 0

    def estimate_tokens(self, messages: List[Message]) -> int:
        """Estimate token count for messages."""
        # Simple estimation: ~4 chars per token
        total_chars = 0
        for msg in messages:
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            elif isinstance(msg.content, list):
                for part in msg.content:
                    if isinstance(part, dict) and "text" in part:
                        total_chars += len(part["text"])

        # Add overhead for tool calls
        for msg in messages:
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total_chars += len(json.dumps(tc.function))

        return total_chars // 4

    def should_compact(self, messages: List[Message]) -> bool:
        """Check if compaction is needed."""
        tokens = self.estimate_tokens(messages)
        threshold = self.config.max_tokens * self.config.compact_threshold
        return tokens >= threshold

    def compact(
        self,
        messages: List[Message],
        focus: Optional[str] = None,
    ) -> Tuple[List[Message], ContextSummary]:
        """Compact messages and return new list with summary."""
        original_count = len(messages)

        if original_count <= self.config.preserve_recent_messages:
            return messages, ContextSummary(
                original_messages=original_count,
                compacted_messages=0,
                preserved_messages=original_count,
            )

        # Strategy: remove old tool outputs, preserve user requests
        preserved: List[Message] = []
        removed: List[Message] = []

        # Keep recent messages
        recent = messages[-self.config.preserve_recent_messages:]

        # Process older messages
        older = messages[:-self.config.preserve_recent_messages]

        for msg in older:
            should_keep = False

            # Preserve user requests
            if self.config.preserve_user_requests and msg.role == "user":
                should_keep = True

            # Preserve system messages with important context
            if msg.role == "system" and focus:
                # Check if message contains focus keywords
                content = str(msg.content) if msg.content else ""
                if focus.lower() in content.lower():
                    should_keep = True

            # Preserve assistant messages with code snippets
            if self.config.preserve_code_snippets and msg.role == "assistant":
                content = str(msg.content) if msg.content else ""
                if "```" in content:
                    should_keep = True

            if should_keep:
                preserved.append(msg)
            else:
                # Remove tool outputs and old assistant messages
                if msg.role in ("tool", "assistant"):
                    removed.append(msg)
                else:
                    preserved.append(msg)

        # Combine preserved + recent
        new_messages = preserved + recent

        # Create summary of removed content
        summary_text = None
        if removed:
            summary_text = self._create_summary(removed, focus)

        self._compaction_count += 1
        self._last_compaction_time = time.time()

        return new_messages, ContextSummary(
            original_messages=original_count,
            compacted_messages=len(removed),
            preserved_messages=len(new_messages),
            summary_text=summary_text,
            compaction_ratio=len(new_messages) / original_count if original_count > 0 else 1.0,
        )

    def _create_summary(
        self,
        removed: List[Message],
        focus: Optional[str] = None,
    ) -> str:
        """Create a summary of removed messages."""
        # Group by type
        tool_outputs: List[str] = []
        assistant_responses: List[str] = []

        for msg in removed:
            if msg.role == "tool":
                tool_outputs.append(f"- Tool: {msg.name}")
            elif msg.role == "assistant":
                content = str(msg.content)[:100] if msg.content else ""
                assistant_responses.append(f"- Assistant: {content}...")

        summary_parts: List[str] = ["[Context compaction summary]"]
        if tool_outputs:
            summary_parts.append("Removed tool outputs:")
            summary_parts.extend(tool_outputs[:10])  # Limit to 10
        if assistant_responses:
            summary_parts.append("Removed assistant messages:")
            summary_parts.extend(assistant_responses[:5])

        if focus:
            summary_parts.append(f"Focus preserved: {focus}")

        return "\n".join(summary_parts)

    def get_compaction_stats(self) -> Dict[str, Any]:
        """Get compaction statistics."""
        return {
            "compaction_count": self._compaction_count,
            "last_compaction_time": self._last_compaction_time,
            "config": {
                "max_tokens": self.config.max_tokens,
                "compact_threshold": self.config.compact_threshold,
            },
        }

    def check_thrashing(self, time_window: float = 60.0) -> bool:
        """Check if compaction is thrashing (multiple rapid compactions)."""
        if self._compaction_count < 3:
            return False

        # Check if 3+ compactions in last minute
        now = time.time()
        return (now - self._last_compaction_time) < time_window and self._compaction_count >= 3