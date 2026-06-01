"""Configuration loader for the Ollama compatibility layer.

Reads ``[ollama_compat]`` from the Aurora TOML config and exposes an
immutable configuration object.  Environment variables override TOML
values for deployment flexibility.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Default model name reported to Ollama clients — env-overridable.
_ENV_MODEL_NAME = os.getenv("OLLAMA_EMULATING_MODEL_NAME", "aurora")
_ENV_MODEL_TAG = os.getenv("OLLAMA_EMULATING_MODEL_TAG", "latest")
_ENV_DEFAULT_KB = os.getenv("OLLAMA_DEFAULT_KB", "default")


@dataclass(frozen=True)
class OllamaCompatConfig:
    """Immutable configuration for the Ollama compat layer."""

    enabled: bool = True
    default_model: str = _ENV_MODEL_NAME
    default_tag: str = _ENV_MODEL_TAG
    default_kb: str = _ENV_DEFAULT_KB
    model_mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def full_model_name(self) -> str:
        """Return ``name:tag`` as a single string."""
        return f"{self.default_model}:{self.default_tag}"

    def resolve_kb(self, model_name: str) -> str:
        """Map an Ollama model name to an Aurora knowledge base name.

        Falls back to ``default_kb`` when no explicit mapping exists.
        """
        # Strip tag suffix if present (e.g. "aurora:latest" → "aurora")
        bare = model_name.split(":")[0] if ":" in model_name else model_name
        return self.model_mapping.get(bare, self.default_kb)

    def list_models(self) -> list[str]:
        """Return all configured model names (including the default)."""
        names = {self.default_model, *self.model_mapping.keys()}
        return sorted(names)


def load_ollama_config(config_path: str | Path | None = None) -> OllamaCompatConfig:
    """Load Ollama compat configuration.

    Priority: environment variables > TOML ``[ollama_compat]`` > defaults.
    """
    toml_section: dict[str, Any] = {}

    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    logger.warning("tomllib/tomli not available; skipping TOML config")
                    return _build_config_from_env({})

            with open(path, "rb") as fh:
                data = tomllib.load(fh)
            toml_section = data.get("ollama_compat", {})

    return _build_config_from_env(toml_section)


def _build_config_from_env(toml_section: dict[str, Any]) -> OllamaCompatConfig:
    """Merge TOML section with environment overrides."""
    enabled = toml_section.get("enabled", True)
    default_model = os.getenv(
        "OLLAMA_EMULATING_MODEL_NAME",
        toml_section.get("default_model", "aurora"),
    )
    default_tag = os.getenv(
        "OLLAMA_EMULATING_MODEL_TAG",
        toml_section.get("default_tag", "latest"),
    )
    default_kb = os.getenv(
        "OLLAMA_DEFAULT_KB",
        toml_section.get("default_kb", "default"),
    )
    model_mapping = dict(toml_section.get("model_mapping", {}))

    return OllamaCompatConfig(
        enabled=enabled,
        default_model=default_model,
        default_tag=default_tag,
        default_kb=default_kb,
        model_mapping=model_mapping,
    )


# ── Module-level singleton ──────────────────────────────────────────

_config: OllamaCompatConfig | None = None


def get_config() -> OllamaCompatConfig:
    """Return the module-level config singleton (lazy-initialised)."""
    global _config
    if _config is None:
        # Try common config paths
        for candidate in (
            Path("configs/aurora.toml"),
            Path("../configs/aurora.toml"),
        ):
            if candidate.exists():
                _config = load_ollama_config(candidate)
                return _config
        _config = load_ollama_config()
    return _config


def set_config(config: OllamaCompatConfig) -> None:
    """Override the module-level config singleton (for testing or app init)."""
    global _config
    _config = config
