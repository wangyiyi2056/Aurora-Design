from typing import List

from aurora_core.agent.base import BaseAgent, AgentMessage


class ManagerAgent(BaseAgent):
    """Manager that delegates to worker agents."""

    def __init__(self, workers: List[BaseAgent]):
        self.workers = {w.__class__.__name__: w for w in workers}

    async def run(self, user_input: str) -> AgentMessage:
        # Simple round-robin delegation for Phase 3
        for worker in self.workers.values():
            return await worker.run(user_input)
        return AgentMessage(role="assistant", content="No workers available.")

    async def plan(self, task: str) -> list:
        return []

    async def observation(self, action_results: List[str]) -> str:
        return "\n".join(action_results)
