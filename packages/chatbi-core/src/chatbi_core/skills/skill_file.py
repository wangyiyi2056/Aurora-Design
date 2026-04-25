"""Skill File definition for ChatBI."""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SkillFile:
    """A skill defined in a Markdown file, following Claude Code patterns.

    Skills:
    - Are defined in .chatbi/skills/*/SKILL.md
    - Load on demand (description only at session start)
    - Can be shared across team
    - Support disable-model-invocation for manual-only use
    """

    name: str
    description: str
    content: str  # Full skill content/instructions
    file_path: Optional[str] = None
    triggers: List[str] = field(default_factory=list)  # When to invoke
    disable_model_invocation: bool = False  # Manual-only
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API."""
        return {
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "file_path": self.file_path,
            "triggers": self.triggers,
            "disable_model_invocation": self.disable_model_invocation,
        }

    @classmethod
    def from_markdown(cls, content: str, file_path: Optional[str] = None) -> "SkillFile":
        """Parse from SKILL.md format."""
        lines = content.strip().split("\n")
        frontmatter: Dict[str, str] = {}
        body_lines: List[str] = []
        in_frontmatter = False

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

        # Parse triggers
        triggers_str = frontmatter.get("triggers", "")
        if triggers_str:
            triggers = [t.strip() for t in triggers_str.split(",")]
        else:
            triggers = []

        return cls(
            name=frontmatter.get("name", "unknown"),
            description=frontmatter.get("description", ""),
            content="\n".join(body_lines),
            file_path=file_path,
            triggers=triggers,
            disable_model_invocation=frontmatter.get("disable-model-invocation", "").lower() == "true",
        )

    def to_markdown(self) -> str:
        """Convert to SKILL.md format."""
        triggers_str = ", ".join(self.triggers)
        disable_str = str(self.disable_model_invocation).lower()

        return f"""---
name: {self.name}
description: {self.description}
triggers: {triggers_str}
disable-model-invocation: {disable_str}
---

{self.content}
"""

    def get_description_only(self) -> str:
        """Get minimal description for session start context."""
        return f"Skill: {self.name} - {self.description}"

    def estimate_token_cost(self) -> int:
        """Estimate token cost for this skill."""
        # Description ~10 tokens, full content ~length/4
        return len(self.content) // 4 + 10