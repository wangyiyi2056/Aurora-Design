"""Session schema definitions."""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class SessionMessage:
    """A message in a session, following Claude Code JSONL format."""
    type: str  # "user", "assistant", "tool_use", "tool_result"
    content: Any
    role: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())

    def to_jsonl(self) -> str:
        """Convert to JSONL format string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_jsonl(cls, line: str) -> "SessionMessage":
        """Parse from JSONL format string."""
        data = json.loads(line)
        return cls(**data)


@dataclass
class Session:
    """A Aurora session with persistence support."""
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New Chat"
    project_path: str = ""
    branch: str = "main"
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    messages: List[SessionMessage] = field(default_factory=list)
    checkpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # file_path -> snapshot
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: SessionMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = time.time()

    def derive_title(self) -> str:
        """Derive title from first user message."""
        for msg in self.messages:
            if msg.type == "user":
                text = str(msg.content) if msg.content else ""
                return text[:50] + ("..." if len(text) > 50 else "")
        return self.title or "New Chat"

    @property
    def message_count(self) -> int:
        """Return the number of messages in this session."""
        return len(self.messages)

    def add_checkpoint(self, file_path: str, content: str) -> None:
        """Add a file checkpoint for rollback support."""
        self.checkpoints[file_path] = {
            "content": content,
            "timestamp": time.time(),
        }
        self.updated_at = time.time()

    def get_checkpoint(self, file_path: str) -> Optional[str]:
        """Get checkpoint content for a file."""
        checkpoint = self.checkpoints.get(file_path)
        return checkpoint["content"] if checkpoint else None

    def rollback_checkpoint(self, file_path: str) -> Optional[str]:
        """Rollback to checkpoint and remove it."""
        content = self.get_checkpoint(file_path)
        if content:
            del self.checkpoints[file_path]
        return content