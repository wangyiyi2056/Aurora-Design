from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Action:
    name: str
    args: Dict[str, Any]


@dataclass
class AgentMessage:
    role: str
    content: str
    actions: List[Action] | None = None
    metadata: Dict[str, Any] | None = None


class BaseAgent(ABC):
    @abstractmethod
    async def run(self, user_input: str) -> AgentMessage:
        """Main entry: plan -> execute actions -> observation -> final answer."""

    @abstractmethod
    async def plan(self, task: str) -> List[Action]:
        """Plan a sequence of actions to complete the task."""

    @abstractmethod
    async def observation(self, action_results: List[str]) -> str:
        """Process action results and generate observation."""
