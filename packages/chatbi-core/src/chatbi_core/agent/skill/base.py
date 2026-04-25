from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseSkill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    def description_cn(self) -> str:
        """Return Chinese description for the skill."""
        return self.description

    @property
    def parameters(self) -> Dict[str, Any]:
        """Return JSON Schema for the skill's parameters (OpenAI function style)."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def is_builtin(self) -> bool:
        """Return whether this skill is built-in (pre-registered by the system)."""
        return True

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Return skill metadata as a dictionary for API responses."""
        return {
            "name": self.name,
            "description": self.description,
            "description_cn": self.description_cn,
            "parameters": self.parameters,
            "is_builtin": self.is_builtin,
        }


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not found")
        return self._skills[name]

    def list_skills(self) -> Dict[str, str]:
        return {name: skill.description for name, skill in self._skills.items()}

    def list_skills_detail(self) -> list[Dict[str, Any]]:
        """Return all skills with full metadata."""
        return [skill.to_dict() for skill in self._skills.values()]
