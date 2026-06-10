"""TOML-driven, per-role LLM configuration with environment variable overrides.

This module bridges the TOML ``[llm_roles]`` configuration section to the
existing :class:`~aurora_core.model.roles.LLMRoleRegistry`. It supports:

* Loading role-specific model, adapter type, temperature, max_tokens, etc.
* Environment variable overrides following the pattern
  ``AURORA_LLM_<ROLE>_<FIELD>`` (e.g. ``AURORA_LLM_EXTRACT_API_KEY``).
* Hot-reload via :meth:`LLMRoleConfigManager.reload`.
* Graceful fallback: roles absent from the config fall back to the default
  LLM registered in the underlying :class:`ModelRegistry`.

Example TOML fragment::

    [llm_roles]
    [llm_roles.extract]
    model = "gpt-4"
    api_key = "sk-..."
    api_base = "https://api.openai.com/v1"
    temperature = 0.3

    [llm_roles.query]
    model = "gpt-3.5-turbo"
    temperature = 0.7

    [llm_roles.keywords]
    model = "gpt-4"
    temperature = 0.2

    [llm_roles.vlm]
    model = "gpt-4-vision-preview"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from aurora_core.config.loader import load_toml_config
from aurora_core.model.roles import LLMRole, RoleLLMConfig

logger = logging.getLogger(__name__)


# Keys we read from each ``[llm_roles.<role>]`` table. The value type hints
# are used by :func:`_coerce_field` to normalise string env-var values.
_FIELD_TYPES: Dict[str, type] = {
    "model": str,
    "model_name": str,
    "model_type": str,
    "api_key": str,
    "api_base": str,
    "temperature": float,
    "max_tokens": int,
    "max_async": int,
    "timeout": int,
    "extra": dict,
}

# Env var pattern: AURORA_LLM_<ROLE>_<FIELD>
_ENV_PREFIX = "AURORA_LLM"


def _coerce_field(field: str, value: str) -> Any:
    """Coerce a string env-var value to the expected type."""
    target = _FIELD_TYPES.get(field, str)
    if target is bool:
        return value.lower() in ("1", "true", "yes", "on")
    if target is int:
        return int(value)
    if target is float:
        return float(value)
    return value


def _env_key(role: str, field: str) -> str:
    """Build the env var name for a role + field pair."""
    return f"{_ENV_PREFIX}_{role.upper()}_{field.upper()}"


@dataclass(frozen=True)
class _ResolvedRoleConfig:
    """Fully resolved (TOML + env) config for a single role."""

    role: LLMRole
    model_name: str
    model_type: str = "openai"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    max_async: int = 4
    timeout: int = 180
    extra: Dict[str, Any] | None = None

    def to_role_llm_config(self) -> RoleLLMConfig:
        kwargs: Dict[str, Any] = {}
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        kwargs["temperature"] = self.temperature
        if self.extra:
            kwargs["extra"] = self.extra

        return RoleLLMConfig(
            model_name=self.model_name,
            model_type=self.model_type,
            max_async=self.max_async,
            timeout=self.timeout,
            kwargs=kwargs,
        )


# Normalise TOML keys that differ from the enum value.
_ROLE_ALIASES: Dict[str, str] = {
    "keyword": "keywords",
    "extraction": "extract",
    "vision": "vlm",
    "multimodal": "vlm",
}


def _normalise_role_key(key: str) -> Optional[LLMRole]:
    """Return the :class:`LLMRole` for a TOML/env key, or ``None`` if unknown."""
    normalised = _ROLE_ALIASES.get(key.lower(), key.lower())
    try:
        return LLMRole(normalised)
    except ValueError:
        logger.warning("Unknown LLM role key '%s' — skipping", key)
        return None


class LLMRoleConfigManager:
    """Load, resolve, and apply per-role LLM configuration.

    Resolution order (later wins):

    1. Defaults hard-coded in :class:`_ResolvedRoleConfig`.
    2. Values from the TOML ``[llm_roles.<role>]`` table.
    3. Environment variables (``AURORA_LLM_<ROLE>_<FIELD>``).

    Parameters
    ----------
    role_configs:
        The ``[llm_roles]`` dict from the TOML file. Keys are role names,
        values are dicts of role settings.
    config_path:
        Optional path to the TOML file. Only used by :meth:`reload`.
    """

    def __init__(
        self,
        role_configs: Dict[str, Dict[str, Any]] | None = None,
        *,
        config_path: str | None = None,
    ) -> None:
        self._raw_configs: Dict[str, Dict[str, Any]] = dict(role_configs or {})
        self._config_path = config_path
        self._resolved: Dict[LLMRole, _ResolvedRoleConfig] = {}
        self._resolve_all()

    # ── Public API ────────────────────────────────────────────────

    def get_config(self, role: LLMRole) -> Optional[_ResolvedRoleConfig]:
        """Return the resolved config for *role*, or ``None`` if not configured."""
        return self._resolved.get(role)

    def get_role_llm_config(self, role: LLMRole) -> Optional[RoleLLMConfig]:
        """Return a :class:`RoleLLMConfig` ready for the registry, or ``None``."""
        resolved = self._resolved.get(role)
        return resolved.to_role_llm_config() if resolved else None

    def configured_roles(self) -> list[LLMRole]:
        """Return the list of roles that have explicit configuration."""
        return list(self._resolved.keys())

    async def apply_to(self, role_registry: Any) -> None:
        """Apply all resolved configs to *role_registry*.

        Parameters
        ----------
        role_registry:
            An :class:`~aurora_core.model.roles.LLMRoleRegistry` instance.
        """
        for role, resolved in self._resolved.items():
            try:
                await role_registry.update_role_config(
                    role, resolved.to_role_llm_config()
                )
            except Exception:
                logger.exception(
                    "Failed to apply role config for '%s'", role.value
                )

    def reload(self) -> None:
        """Re-read the TOML file (if *config_path* was given) and re-resolve.

        Env vars are re-read on every reload, so runtime env changes take
        effect immediately.
        """
        if self._config_path and Path(self._config_path).exists():
            data = load_toml_config(self._config_path)
            self._raw_configs = dict(data.get("llm_roles", {}))
            logger.info(
                "Reloaded LLM role configs from %s (%d roles)",
                self._config_path,
                len(self._raw_configs),
            )
        self._resolved.clear()
        self._resolve_all()

    # ── Internal ──────────────────────────────────────────────────

    def _resolve_all(self) -> None:
        for key, raw in self._raw_configs.items():
            role = _normalise_role_key(key)
            if role is None:
                continue
            self._resolved[role] = self._resolve_role(role, raw)

    def _resolve_role(
        self, role: LLMRole, toml_data: Dict[str, Any]
    ) -> _ResolvedRoleConfig:
        """Merge defaults ← TOML ← env vars into a single resolved config."""
        merged: Dict[str, Any] = {}

        # 1. TOML values
        for field in _FIELD_TYPES:
            if field in toml_data:
                merged[field] = toml_data[field]

        # 2. Env var overrides (always win)
        for field in _FIELD_TYPES:
            env_val = os.environ.get(_env_key(role.value, field))
            if env_val is not None:
                merged[field] = _coerce_field(field, env_val)

        # Normalise model vs model_name — accept either
        model_name = merged.get("model_name") or merged.get("model", "")
        if not model_name:
            logger.warning(
                "Role '%s' has no model configured — skipping", role.value
            )
            # Return a sentinel that will be filtered out
            return _ResolvedRoleConfig(
                role=role, model_name="__missing__"
            )

        return _ResolvedRoleConfig(
            role=role,
            model_name=model_name,
            model_type=merged.get("model_type", "openai"),
            api_key=merged.get("api_key"),
            api_base=merged.get("api_base"),
            temperature=float(merged.get("temperature", 0.7)),
            max_tokens=merged.get("max_tokens"),
            max_async=int(merged.get("max_async", 4)),
            timeout=int(merged.get("timeout", 180)),
            extra=merged.get("extra"),
        )

    @classmethod
    def from_toml(cls, config_path: str) -> "LLMRoleConfigManager":
        """Create a manager by reading the TOML file at *config_path*."""
        data = load_toml_config(config_path)
        return cls(
            role_configs=data.get("llm_roles", {}),
            config_path=config_path,
        )
