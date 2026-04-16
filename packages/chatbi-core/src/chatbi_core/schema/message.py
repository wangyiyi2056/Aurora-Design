from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelOutput:
    text: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
