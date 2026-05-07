"""Dynamic context assembly for system prompt injection.

Mirrors Claude-Code's context.ts pattern:
- User context (CLAUDE.md, date) injected as <system-reminder> user message
- System context (git status) appended to system prompt
- Project context (directory structure, branch) in environment section
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class PromptContext:
    """Complete prompt context assembled from environment and configuration."""

    # User context (injected as <system-reminder>)
    current_date: str = ""
    claude_md_content: str = ""

    # System context (appended to system prompt)
    git_status: str = ""

    # Memory context
    memory_context: str = ""

    # Skills context
    skills_context: str = ""

    # Project metadata
    project_root: str = ""
    platform: str = ""
    shell: str = ""
    python_version: str = ""

    def to_user_context(self) -> str:
        parts = []
        if self.current_date:
            parts.append(self.current_date)
        if self.claude_md_content:
            parts.append(self.claude_md_content)
        return "\n\n".join(parts)

    def to_system_context(self) -> str:
        return self.git_status


class ContextProvider:
    """Loads and assembles all context for prompt injection.

    Usage::

        provider = ContextProvider(project_root="/path/to/project")
        ctx = provider.assemble()
        # Inject ctx.to_user_context() as a <system-reminder> user message
        # Append ctx.to_system_context() to the system prompt
    """

    def __init__(
        self,
        project_root: str,
        memory_manager=None,
        skill_registry=None,
    ):
        self.project_root = Path(project_root).resolve()
        self.memory_manager = memory_manager
        self.skill_registry = skill_registry

    def assemble(self, tools: Optional[List] = None) -> PromptContext:
        ctx = PromptContext()

        # Date
        ctx.current_date = get_date_context()

        # CLAUDE.md
        ctx.claude_md_content = get_claude_md_context(self.project_root)

        # Git
        ctx.git_status = get_git_context(self.project_root)

        # Memory
        if self.memory_manager:
            ctx.memory_context = get_memory_context(self.memory_manager)

        # Skills
        if self.skill_registry:
            ctx.skills_context = self._get_skills_context()

        # Environment
        ctx.project_root = str(self.project_root)
        ctx.platform = os.uname().sysname if hasattr(os, "uname") else ""
        ctx.shell = os.environ.get("SHELL", "")
        ctx.python_version = (
            f"{os.uname().sysname} {os.uname().release}"
            if hasattr(os, "uname")
            else ""
        )

        return ctx

    def _get_skills_context(self) -> str:
        """Build a summary of available skills."""
        if not self.skill_registry:
            return ""
        try:
            skills = self.skill_registry.list_skills()
            lines = ["Available skills:"]
            for s in skills[:30]:
                name = s.get("name", s) if isinstance(s, dict) else s.name
                desc = s.get("description", "") if isinstance(s, dict) else getattr(s, "description", "")
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
            return "\n".join(lines)
        except Exception:
            return ""


def get_date_context() -> str:
    """Return today's date in ISO format for prompt injection."""
    today = date.today()
    return f"Today's date is {today.isoformat()}."


def get_git_context(project_root: Path) -> str:
    """Get git status context for the system prompt.

    Mirrors Claude-Code's getSystemContext() in context.ts.
    """
    if not (project_root / ".git").exists():
        return ""

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status_output = result.stdout[:2000] if result.stdout else ""

        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = branch_result.stdout.strip()

        main_result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if main_result.returncode == 0:
            main_branch = main_result.stdout.strip().replace("refs/remotes/origin/", "")
        else:
            main_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "main"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            main_branch = "main" if main_result.returncode == 0 else ""

        user_result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_user = user_result.stdout.strip()

        # Recent commits
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        recent_commits = log_result.stdout.strip()

        parts = [f"This is the git status at the start of the conversation."]
        if branch:
            parts.append(f"Current branch: {branch}")
        if main_branch:
            parts.append(f"Main branch: {main_branch}")
        if git_user:
            parts.append(f"Git user: {git_user}")
        if status_output:
            parts.append(f"\nWorking tree status:\n{status_output}")
        if recent_commits:
            parts.append(f"\nRecent commits:\n{recent_commits}")

        return "\n".join(parts)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def get_claude_md_context(project_root: Path) -> str:
    """Load CLAUDE.md and related project instruction files.

    Mirrors Claude-Code's CLAUDE.md loading in claudemd.ts.
    Loads:
    1. ~/.claude/CLAUDE.md (user-level)
    2. <project_root>/CLAUDE.md (project-level)
    3. <project_root>/.claude/CLAUDE.md
    4. <project_root>/CLAUDE.local.md (local overrides, not in git)
    """
    files_to_check: List[Tuple[Path, str]] = []

    # User-level CLAUDE.md
    user_claude = Path.home() / ".claude" / "CLAUDE.md"
    if user_claude.exists():
        files_to_check.append((user_claude, "project instructions (user)"))

    # Project-level CLAUDE.md files (closest to root first)
    current = project_root.resolve()
    while current != current.parent:
        claude_md = current / "CLAUDE.md"
        if claude_md.exists():
            desc = "project instructions, checked into the codebase"
            if current != project_root:
                try:
                    desc += f" at {current.relative_to(project_root)}"
                except ValueError:
                    desc += f" at {current}"
            files_to_check.append((claude_md, desc))

        dot_claude = current / ".claude" / "CLAUDE.md"
        if dot_claude.exists():
            files_to_check.append((dot_claude, "project instructions"))

        current = current.parent

    # CLAUDE.local.md
    local_claude = project_root / "CLAUDE.local.md"
    if local_claude.exists():
        files_to_check.append((local_claude, "local-only instructions (not in git)"))

    if not files_to_check:
        return ""

    parts = []
    for file_path, desc in files_to_check:
        try:
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"Contents of {file_path} ({desc}):\n\n{content}")
        except Exception:
            continue

    return "\n\n".join(parts)


def get_memory_context(memory_manager) -> str:
    """Get combined memory context."""
    try:
        return memory_manager.get_memory_context()
    except Exception:
        return ""


def get_project_context(project_root: Path) -> str:
    """Get project directory structure overview."""
    if not project_root.exists():
        return ""
    try:
        items = sorted(project_root.iterdir())
        # Filter hidden files except key ones
        visible = [
            p for p in items
            if not p.name.startswith(".") or p.name in (".git", ".claude", ".github")
        ][:50]
        lines = ["Project root contents:"]
        for p in visible:
            suffix = "/" if p.is_dir() else ""
            lines.append(f"  {p.name}{suffix}")
        return "\n".join(lines)[:2000]
    except Exception:
        return ""
