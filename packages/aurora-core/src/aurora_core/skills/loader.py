"""Skills Loader for Aurora - loads skills from Markdown files."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from aurora_core.skills.skill_file import SkillFile


@dataclass
class SkillSearchResult:
    """Result from skill search."""
    skills: List[SkillFile]
    query: str
    total_available: int


class SkillsLoader:
    """Loads skills from .aurora/skills/ directories.

    Skills are organized in subdirectories with SKILL.md files:
    .aurora/skills/
    ├── data-analysis/
    │   └── SKILL.md
    ├── sql-query/
    │   └── SKILL.md
    """

    def __init__(
        self,
        project_skills_path: Optional[str] = None,
        global_skills_path: Optional[str] = None,
    ):
        self.project_skills_path = Path(
            project_skills_path or ".aurora/skills"
        )
        self.global_skills_path = Path(
            global_skills_path or os.path.expanduser("~/.aurora/skills")
        )

        self._skills: Dict[str, SkillFile] = {}
        self._descriptions_loaded: bool = False

    def _discover_skills(self) -> List[Path]:
        """Discover all SKILL.md files."""
        skill_files: List[Path] = []

        # Global skills
        if self.global_skills_path.exists():
            for skill_dir in self.global_skills_path.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        skill_files.append(skill_md)

        # Project skills (override global)
        if self.project_skills_path.exists():
            for skill_dir in self.project_skills_path.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        skill_files.append(skill_md)

        return skill_files

    def load_descriptions(self) -> Dict[str, str]:
        """Load only skill descriptions for session start context."""
        descriptions: Dict[str, str] = {}

        for skill_path in self._discover_skills():
            try:
                # Read first 100 lines to get frontmatter
                with open(skill_path) as f:
                    first_lines = []
                    for i, line in enumerate(f):
                        if i >= 100:
                            break
                        first_lines.append(line)

                content = "".join(first_lines)
                skill = SkillFile.from_markdown(content, str(skill_path))

                # Store description only
                descriptions[skill.name] = skill.description
                self._skills[skill.name] = skill  # Store partial

            except Exception:
                continue

        self._descriptions_loaded = True
        return descriptions

    def load_skill(self, name: str) -> Optional[SkillFile]:
        """Load full skill content on demand."""
        # Check if already loaded
        skill = self._skills.get(name)
        if skill and len(skill.content) > 100:
            return skill

        # Find and load full skill
        for skill_path in self._discover_skills():
            try:
                full_content = skill_path.read_text()
                skill = SkillFile.from_markdown(full_content, str(skill_path))

                if skill.name == name:
                    self._skills[name] = skill
                    return skill

            except Exception:
                continue

        return None

    def get_skill(self, name: str) -> Optional[SkillFile]:
        """Get a skill by name."""
        return self._skills.get(name)

    def search(self, query: str, limit: int = 10) -> SkillSearchResult:
        """Search for skills matching query."""
        matching: List[SkillFile] = []

        query_lower = query.lower()
        for name, skill in self._skills.items():
            # Match name or description
            if query_lower in name.lower():
                matching.append(skill)
            elif query_lower in skill.description.lower():
                matching.append(skill)

        # Sort by relevance
        matching.sort(key=lambda s: (
            0 if query_lower in s.name.lower() else 1,
            s.name,
        ))

        return SkillSearchResult(
            skills=matching[:limit],
            query=query,
            total_available=len(self._skills),
        )

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all skills with descriptions."""
        return [
            {"name": name, "description": skill.description}
            for name, skill in self._skills.items()
        ]

    def list_skills_detail(self) -> List[Dict[str, Any]]:
        """List all skills with full metadata."""
        return [skill.to_dict() for skill in self._skills.values()]

    def get_description_context(self) -> str:
        """Get minimal context with skill descriptions."""
        if not self._descriptions_loaded:
            self.load_descriptions()

        lines: List[str] = ["Available skills:"]
        for name, skill in self._skills.items():
            lines.append(f"- {name}: {skill.description}")

        return "\n".join(lines)

    def estimate_context_cost(self) -> Dict[str, int]:
        """Estimate token usage."""
        description_cost = sum(
            len(skill.description) // 4 + 5
            for skill in self._skills.values()
        )

        full_cost = sum(
            skill.estimate_token_cost()
            for skill in self._skills.values()
        )

        return {
            "description_cost": description_cost,
            "full_cost": full_cost,
            "savings": full_cost - description_cost,
        }

    def register_skill(self, skill: SkillFile) -> str:
        """Register a skill and save to file."""
        # Determine save path
        skill_dir = self.project_skills_path / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(skill.to_markdown())

        skill.file_path = str(skill_md)
        self._skills[skill.name] = skill

        return str(skill_md)

    def delete_skill(self, name: str) -> bool:
        """Delete a skill."""
        skill = self._skills.get(name)
        if not skill:
            return False

        if skill.file_path:
            skill_path = Path(skill.file_path)
            skill_dir = skill_path.parent

            # Remove file and directory
            skill_path.unlink(missing_ok=True)
            try:
                skill_dir.rmdir()
            except Exception:
                pass

        del self._skills[name]
        return True