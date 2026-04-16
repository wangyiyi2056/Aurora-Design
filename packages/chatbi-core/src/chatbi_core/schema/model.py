from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LLMConfig:
    model_name: str
    model_type: str  # e.g. "openai", "proxy", "transformers"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    extra: Dict[str, Any] = field(default_factory=dict)
