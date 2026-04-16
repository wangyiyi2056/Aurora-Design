from abc import ABC, abstractmethod
from typing import Any


class BaseOperator(ABC):
    @abstractmethod
    async def execute(self, input_value: Any) -> Any:
        ...
