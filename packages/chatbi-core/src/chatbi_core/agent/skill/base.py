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
    def parameters(self) -> Dict[str, Any]:
        """Return JSON Schema for the skill's parameters (OpenAI function style)."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        ...


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
