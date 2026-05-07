"""Subagent Definition for Aurora."""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SubagentDefinition:
    """Definition of a subagent following Claude Code patterns.

    Subagents have:
    - Independent context (separate from main conversation)
    - Specialized tools (subset of available tools)
    - Custom prompts for specialized tasks
    - Return summary to main agent when done
    """

    name: str
    description: str
    prompt: str
    tools: List[str] = field(default_factory=list)  # Allowed tools
    model: Optional[str] = None  # Model override
    max_context_tokens: int = 50000  # Smaller context for subagents
    timeout_seconds: int = 300  # Execution timeout
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API."""
        return {
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "tools": self.tools,
            "model": self.model,
            "max_context_tokens": self.max_context_tokens,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_markdown(cls, content: str) -> "SubagentDefinition":
        """Parse from Markdown definition file."""
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

        # Parse tools as comma-separated or list
        tools_str = frontmatter.get("tools", "")
        if tools_str:
            # Handle both "Read,Edit,Bash" and ["Read","Edit","Bash"]
            if tools_str.startswith("["):
                tools_str = re.sub(r'[\[\]"]', "", tools_str)
                tools = [t.strip() for t in tools_str.split(",")]
            else:
                tools = [t.strip() for t in tools_str.split(",")]
        else:
            tools = []

        return cls(
            name=frontmatter.get("name", "unknown"),
            description=frontmatter.get("description", ""),
            prompt="\n".join(body_lines),
            tools=tools,
            model=frontmatter.get("model"),
            max_context_tokens=int(frontmatter.get("max_context_tokens", 50000)),
            timeout_seconds=int(frontmatter.get("timeout_seconds", 300)),
        )

    def to_markdown(self) -> str:
        """Convert to Markdown definition file format."""
        tools_str = ", ".join(self.tools)
        return f"""---
name: {self.name}
description: {self.description}
tools: {tools_str}
model: {self.model or ""}
max_context_tokens: {self.max_context_tokens}
timeout_seconds: {self.timeout_seconds}
---

{self.prompt}
"""