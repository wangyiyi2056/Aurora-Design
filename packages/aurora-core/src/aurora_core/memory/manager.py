"""Memory Manager for Aurora - handles persistent memory."""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aurora_core.memory.schema import MemoryEntry, MemoryType


class MemoryManager:
    """Manages persistent memory following Claude Code patterns.

    Memory is stored in Markdown files under ~/.aurora/memory/
    and project-level .aurora/memory/
    """

    DEFAULT_MEMORY_LIMIT_LINES = 200
    DEFAULT_MEMORY_LIMIT_BYTES = 25000

    def __init__(
        self,
        global_path: Optional[str] = None,
        project_path: Optional[str] = None,
    ):
        self.global_path = Path(global_path or os.path.expanduser("~/.aurora/memory"))
        self.project_path = Path(project_path) if project_path else None

        self.global_path.mkdir(parents=True, exist_ok=True)
        if self.project_path:
            memory_path = self.project_path / ".aurora" / "memory"
            memory_path.mkdir(parents=True, exist_ok=True)

        self._memories: Dict[str, MemoryEntry] = {}
        self._load_memories()

    def _load_memories(self) -> None:
        """Load all memory files from global and project paths."""
        # Load global memories
        for md_file in self.global_path.glob("*.md"):
            if md_file.name == "MEMORY.md":
                continue  # Skip index file
            try:
                content = md_file.read_text()
                entry = MemoryEntry.from_markdown(content, str(md_file))
                self._memories[entry.name] = entry
            except Exception:
                continue

        # Load project memories
        if self.project_path:
            project_memory = self.project_path / ".aurora" / "memory"
            if project_memory.exists():
                for md_file in project_memory.glob("*.md"):
                    if md_file.name == "MEMORY.md":
                        continue
                    try:
                        content = md_file.read_text()
                        entry = MemoryEntry.from_markdown(content, str(md_file))
                        self._memories[entry.name] = entry
                    except Exception:
                        continue

    def save_memory(self, entry: MemoryEntry) -> str:
        """Save a memory entry."""
        # Determine path based on type
        if entry.type == MemoryType.USER:
            save_path = self.global_path
        else:
            save_path = self.project_path / ".aurora" / "memory" if self.project_path else self.global_path

        file_path = save_path / f"{entry.name}.md"
        file_path.write_text(entry.to_markdown())

        entry.file_path = str(file_path)
        entry.updated_at = time.time()
        self._memories[entry.name] = entry

        self._update_memory_index()
        return str(file_path)

    def _update_memory_index(self) -> None:
        """Update MEMORY.md index file."""
        index_path = self.global_path / "MEMORY.md"

        lines: List[str] = ["# Aurora Memory Index\n"]
        for name, entry in self._memories.items():
            hook = f"- [{entry.name}]({entry.name}.md) — {entry.description}"
            if len(hook) > 150:
                hook = hook[:147] + "..."
            lines.append(hook)

        # Truncate to limit
        if len(lines) > self.DEFAULT_MEMORY_LIMIT_LINES:
            lines = lines[:self.DEFAULT_MEMORY_LIMIT_LINES]

        content = "\n".join(lines)
        if len(content) > self.DEFAULT_MEMORY_LIMIT_BYTES:
            content = content[:self.DEFAULT_MEMORY_LIMIT_BYTES]

        index_path.write_text(content)

        if self.project_path:
            project_index = self.project_path / ".aurora" / "memory" / "MEMORY.md"
            if project_index.parent.exists():
                project_index.write_text(content)

    def get_memory(self, name: str) -> Optional[MemoryEntry]:
        """Get a memory entry by name."""
        return self._memories.get(name)

    def update_memory(self, name: str, content: str) -> Optional[MemoryEntry]:
        """Update memory content."""
        entry = self._memories.get(name)
        if entry:
            entry.content = content
            entry.updated_at = time.time()
            self.save_memory(entry)
        return entry

    def delete_memory(self, name: str) -> bool:
        """Delete a memory entry."""
        entry = self._memories.get(name)
        if entry and entry.file_path:
            Path(entry.file_path).unlink(missing_ok=True)
            del self._memories[name]
            self._update_memory_index()
            return True
        return False

    def list_memories(
        self,
        type_filter: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """List all memory entries, optionally filtered by type."""
        entries = list(self._memories.values())
        if type_filter:
            entries = [e for e in entries if e.type == type_filter]
        return entries

    def get_memory_context(self) -> str:
        """Get combined memory context for session start."""
        context_parts: List[str] = []

        # User memories first
        user_memories = self.list_memories(MemoryType.USER)
        for entry in user_memories:
            context_parts.append(f"# User: {entry.name}\n{entry.content}")

        # Project memories
        project_memories = self.list_memories(MemoryType.PROJECT)
        for entry in project_memories:
            context_parts.append(f"# Project: {entry.name}\n{entry.content}")

        # Feedback memories
        feedback_memories = self.list_memories(MemoryType.FEEDBACK)
        for entry in feedback_memories:
            context_parts.append(f"# Feedback: {entry.name}\n{entry.content}")

        return "\n\n".join(context_parts)

    def auto_save(
        self,
        type: MemoryType,
        name: str,
        description: str,
        content: str,
    ) -> str:
        """Auto-save a memory entry (used for learned patterns)."""
        # Check if exists
        existing = self.get_memory(name)
        if existing:
            # Append if exists
            existing.content = f"{existing.content}\n\n{content}"
            existing.updated_at = time.time()
            return self.save_memory(existing)
        else:
            # Create new
            entry = MemoryEntry(
                name=name,
                description=description,
                type=type,
                content=content,
            )
            return self.save_memory(entry)