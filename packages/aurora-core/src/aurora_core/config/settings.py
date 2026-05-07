from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aurora_core.config.loader import load_toml_config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AURORA_", extra="ignore")

    app_name: str = "Aurora"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    llm_configs: List[Dict[str, Any]] = Field(default_factory=list)
    default_llm: str = ""
    embedding_configs: List[Dict[str, Any]] = Field(default_factory=list)
    default_embedding: str = ""
    datasource_configs: List[Dict[str, Any]] = Field(default_factory=list)
    default_datasource: str = ""

    @classmethod
    def from_toml(cls, path: str) -> "Settings":
        data = load_toml_config(path)
        return cls(**data)
