import pytest

from aurora_core.agent.base import Action, AgentMessage
from aurora_core.agent.memory.short_term import MemoryItem, ShortTermMemory
from aurora_core.agent.skill.base import BaseSkill, SkillRegistry


class FakeSkill(BaseSkill):
    @property
    def name(self):
        return "echo"

    @property
    def description(self):
        return "Echoes input"

    async def execute(self, **kwargs):
        return kwargs.get("text", "")


def test_skill_registry():
    registry = SkillRegistry()
    registry.register(FakeSkill())
    assert "echo" in registry.list_skills()
    skill = registry.get("echo")
    assert skill.name == "echo"


def test_short_term_memory():
    mem = ShortTermMemory(max_turns=2)
    mem.add(MemoryItem(role="user", content="hi"))
    mem.add(MemoryItem(role="assistant", content="hello"))
    mem.add(MemoryItem(role="user", content="bye"))
    mem.add(MemoryItem(role="assistant", content="goodbye"))
    mem.add(MemoryItem(role="user", content="?"))
    msgs = mem.get_messages()
    assert len(msgs) <= 4  # max_turns * 2
