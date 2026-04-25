"""Memory schema definitions."""

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryType(Enum):
    """Types of memory entries."""
    USER = "user"          # User preferences, role, knowledge
    FEEDBACK = "feedback"  # Guidance on how to approach work
    PROJECT = "project"    # Project context, goals, bugs
    REFERENCE = "reference"  # External system pointers


@dataclass
class MemoryEntry:
    """A memory entry following Claude Code format."""
    name: str
    description: str
    type: MemoryType
    content: str
    file_path: Optional[str] = None
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def to_markdown(self) -> str:
        """Convert to Claude Code memory markdown format."""
        return f"""---
name: {self.name}
description: {self.description}
type: {self.type.value}
---

{self.content}
"""

    @classmethod
    def from_markdown(cls, content: str, file_path: Optional[str] = None) -> "MemoryEntry":
        """Parse from Claude Code memory markdown format."""
        lines = content.strip().split("\n")
        if not lines[0].startswith("---"):
            raise ValueError("Invalid memory format: missing frontmatter")

        # Parse frontmatter
        frontmatter: Dict[str, str] = {}
        in_frontmatter = False
        body_lines: List[str] = []

        for i, line in enumerate(lines):
            if line == "---":
                if i == 0:
                    in_frontmatter = True
                elif in_frontmatter:
                    in_frontmatter = False
                continue
            if in_frontmatter:
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()
            else:
                body_lines.append(line)

        return cls(
            name=frontmatter.get("name", "unknown"),
            description=frontmatter.get("description", ""),
            type=MemoryType(frontmatter.get("type", "user")),
            content="\n".join(body_lines),
            file_path=file_path,
        )