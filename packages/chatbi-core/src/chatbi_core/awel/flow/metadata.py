from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OperatorMetadata:
    name: str
    operator_type: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowMetadata:
    name: str
    operators: List[OperatorMetadata] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)
