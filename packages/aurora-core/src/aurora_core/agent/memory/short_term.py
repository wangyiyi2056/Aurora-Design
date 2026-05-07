from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MemoryItem:
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._history: List[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        self._history.append(item)
        if len(self._history) > self.max_turns * 2:
            self._history = self._history[-self.max_turns * 2 :]

    def get_messages(self) -> List[MemoryItem]:
        return list(self._history)

    def clear(self) -> None:
        self._history = []
