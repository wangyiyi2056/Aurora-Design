from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class BaseParameters:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseParameters":
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered)
