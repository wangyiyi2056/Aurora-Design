"""Tests for the per-role LLM configuration system.

Covers TOML loading, env-var overrides, role aliases, fallback behaviour,
``apply_to`` integration with ``LLMRoleRegistry``, and hot-reload.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from aurora_core.config.settings import Settings
from aurora_core.llm.role_config import (
    LLMRoleConfigManager,
    _coerce_field,
    _env_key,
    _normalise_role_key,
)
from aurora_core.model.roles import LLMRole, LLMRoleRegistry, RoleLLMConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _sample_role_configs() -> dict[str, dict]:
    return {
        "extract": {
            "model": "gpt-4",
            "model_type": "openai",
            "api_key": "sk-extract",
            "api_base": "https://api.openai.com/v1",
            "temperature": 0.3,
            "max_tokens": 4096,
            "max_async": 6,
        },
        "query": {
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
        },
        "keywords": {
            "model": "gpt-4",
            "temperature": 0.2,
        },
        "vlm": {
            "model": "gpt-4-vision-preview",
            "max_async": 2,
        },
    }


# ── Unit tests: pure functions ───────────────────────────────────────────────


def test_env_key_format():
    assert _env_key("extract", "api_key") == "AURORA_LLM_EXTRACT_API_KEY"
    assert _env_key("vlm", "temperature") == "AURORA_LLM_VLM_TEMPERATURE"


def test_coerce_field_int():
    assert _coerce_field("max_tokens", "2048") == 2048
    assert _coerce_field("max_async", "8") == 8


def test_coerce_field_float():
    assert _coerce_field("temperature", "0.3") == pytest.approx(0.3)


def test_coerce_field_str():
    assert _coerce_field("model", "gpt-4") == "gpt-4"
    assert _coerce_field("api_key", "sk-xxx") == "sk-xxx"


def test_normalise_role_key_known():
    assert _normalise_role_key("extract") == LLMRole.EXTRACT
    assert _normalise_role_key("query") == LLMRole.QUERY
    assert _normalise_role_key("keywords") == LLMRole.KEYWORDS
    assert _normalise_role_key("vlm") == LLMRole.VLM


def test_normalise_role_key_aliases():
    assert _normalise_role_key("keyword") == LLMRole.KEYWORDS
    assert _normalise_role_key("extraction") == LLMRole.EXTRACT
    assert _normalise_role_key("vision") == LLMRole.VLM
    assert _normalise_role_key("multimodal") == LLMRole.VLM


def test_normalise_role_key_case_insensitive():
    assert _normalise_role_key("EXTRACT") == LLMRole.EXTRACT
    assert _normalise_role_key("Query") == LLMRole.QUERY


def test_normalise_role_key_unknown(caplog):
    with caplog.at_level("WARNING"):
        result = _normalise_role_key("nonexistent")
    assert result is None
    assert "nonexistent" in caplog.text


# ── LLMRoleConfigManager: basic loading ─────────────────────────────────────


def test_manager_loads_all_roles():
    manager = LLMRoleConfigManager(_sample_role_configs())
    assert set(manager.configured_roles()) == {
        LLMRole.EXTRACT,
        LLMRole.QUERY,
        LLMRole.KEYWORDS,
        LLMRole.VLM,
    }


def test_manager_resolves_model_name():
    manager = LLMRoleConfigManager(_sample_role_configs())
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg is not None
    assert cfg.model_name == "gpt-4"
    assert cfg.model_type == "openai"
    assert cfg.api_key == "sk-extract"
    assert cfg.api_base == "https://api.openai.com/v1"
    assert cfg.temperature == pytest.approx(0.3)
    assert cfg.max_tokens == 4096
    assert cfg.max_async == 6


def test_manager_defaults_for_minimal_config():
    manager = LLMRoleConfigManager({"query": {"model": "gpt-3.5-turbo"}})
    cfg = manager.get_config(LLMRole.QUERY)
    assert cfg is not None
    assert cfg.model_name == "gpt-3.5-turbo"
    assert cfg.model_type == "openai"  # default
    assert cfg.temperature == pytest.approx(0.7)  # default
    assert cfg.max_async == 4  # default


def test_manager_unconfigured_role_returns_none():
    manager = LLMRoleConfigManager({"extract": {"model": "gpt-4"}})
    assert manager.get_config(LLMRole.QUERY) is None
    assert manager.get_role_llm_config(LLMRole.VLM) is None


def test_manager_empty_configs():
    manager = LLMRoleConfigManager({})
    assert manager.configured_roles() == []


def test_manager_none_configs():
    manager = LLMRoleConfigManager(None)
    assert manager.configured_roles() == []


def test_manager_accepts_model_name_key():
    """Both 'model' and 'model_name' should work as the model identifier."""
    manager = LLMRoleConfigManager(
        {"extract": {"model_name": "claude-3-opus", "model_type": "anthropic"}}
    )
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg is not None
    assert cfg.model_name == "claude-3-opus"
    assert cfg.model_type == "anthropic"


def test_manager_accepts_keyword_alias():
    """The TOML key 'keyword' (singular) should map to LLMRole.KEYWORDS."""
    manager = LLMRoleConfigManager({"keyword": {"model": "gpt-4"}})
    assert LLMRole.KEYWORDS in manager.configured_roles()


def test_manager_skips_unknown_role(caplog):
    with caplog.at_level("WARNING"):
        manager = LLMRoleConfigManager(
            {"extract": {"model": "gpt-4"}, "bogus": {"model": "gpt-4"}}
        )
    assert LLMRole.EXTRACT in manager.configured_roles()
    assert len(manager.configured_roles()) == 1


def test_manager_skips_role_without_model(caplog):
    with caplog.at_level("WARNING"):
        manager = LLMRoleConfigManager({"extract": {"temperature": 0.5}})
    # Role is resolved but has sentinel model_name; apply_to would fail
    # gracefully. We check the warning was logged.
    assert "no model" in caplog.text.lower()


# ── Environment variable overrides ──────────────────────────────────────────


def test_env_var_overrides_api_key(monkeypatch):
    monkeypatch.setenv("AURORA_LLM_EXTRACT_API_KEY", "sk-from-env")
    manager = LLMRoleConfigManager(
        {"extract": {"model": "gpt-4", "api_key": "sk-from-toml"}}
    )
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg is not None
    assert cfg.api_key == "sk-from-env"


def test_env_var_overrides_temperature(monkeypatch):
    monkeypatch.setenv("AURORA_LLM_QUERY_TEMPERATURE", "0.9")
    manager = LLMRoleConfigManager(
        {"query": {"model": "gpt-3.5-turbo", "temperature": 0.7}}
    )
    cfg = manager.get_config(LLMRole.QUERY)
    assert cfg is not None
    assert cfg.temperature == pytest.approx(0.9)


def test_env_var_overrides_model(monkeypatch):
    monkeypatch.setenv("AURORA_LLM_VLM_MODEL", "claude-3-vision")
    manager = LLMRoleConfigManager(
        {"vlm": {"model": "gpt-4-vision-preview"}}
    )
    cfg = manager.get_config(LLMRole.VLM)
    assert cfg is not None
    assert cfg.model_name == "claude-3-vision"


def test_env_var_creates_role_from_scratch(monkeypatch):
    """Env vars alone cannot create a role — TOML must declare it."""
    monkeypatch.setenv("AURORA_LLM_EXTRACT_API_KEY", "sk-env-only")
    manager = LLMRoleConfigManager({})
    assert LLMRole.EXTRACT not in manager.configured_roles()


def test_env_var_no_leak_between_roles(monkeypatch):
    monkeypatch.setenv("AURORA_LLM_EXTRACT_API_KEY", "sk-extract-env")
    manager = LLMRoleConfigManager(
        {
            "extract": {"model": "gpt-4", "api_key": "sk-toml"},
            "query": {"model": "gpt-3.5", "api_key": "sk-query-toml"},
        }
    )
    extract_cfg = manager.get_config(LLMRole.EXTRACT)
    query_cfg = manager.get_config(LLMRole.QUERY)
    assert extract_cfg.api_key == "sk-extract-env"
    assert query_cfg.api_key == "sk-query-toml"  # untouched


# ── to_role_llm_config ──────────────────────────────────────────────────────


def test_to_role_llm_config_carries_kwargs():
    manager = LLMRoleConfigManager(_sample_role_configs())
    rlc = manager.get_role_llm_config(LLMRole.EXTRACT)
    assert isinstance(rlc, RoleLLMConfig)
    assert rlc.model_name == "gpt-4"
    assert rlc.model_type == "openai"
    assert rlc.max_async == 6
    assert rlc.kwargs["api_key"] == "sk-extract"
    assert rlc.kwargs["api_base"] == "https://api.openai.com/v1"
    assert rlc.kwargs["temperature"] == pytest.approx(0.3)
    assert rlc.kwargs["max_tokens"] == 4096


def test_to_role_llm_config_omits_none_kwargs():
    manager = LLMRoleConfigManager(
        {"query": {"model": "gpt-3.5-turbo"}}
    )
    rlc = manager.get_role_llm_config(LLMRole.QUERY)
    assert "api_key" not in rlc.kwargs
    assert "api_base" not in rlc.kwargs
    assert "max_tokens" not in rlc.kwargs
    assert rlc.kwargs["temperature"] == pytest.approx(0.7)


# ── apply_to integration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_to_calls_update_role_config():
    manager = LLMRoleConfigManager(
        {"extract": {"model": "gpt-4", "model_type": "openai", "api_key": "sk"}}
    )

    mock_registry = MagicMock()
    mock_registry.update_role_config = AsyncMock()

    await manager.apply_to(mock_registry)

    mock_registry.update_role_config.assert_awaited_once()
    call_role, call_config = mock_registry.update_role_config.call_args[0]
    assert call_role == LLMRole.EXTRACT
    assert isinstance(call_config, RoleLLMConfig)
    assert call_config.model_name == "gpt-4"


@pytest.mark.asyncio
async def test_apply_to_handles_adapter_error_gracefully():
    """If update_role_config raises, apply_to logs and continues."""
    manager = LLMRoleConfigManager(
        {
            "extract": {"model": "gpt-4", "model_type": "openai", "api_key": "sk"},
            "query": {"model": "gpt-3.5", "model_type": "openai"},
        }
    )

    mock_registry = MagicMock()
    # First call raises, second succeeds
    mock_registry.update_role_config = AsyncMock(
        side_effect=[ValueError("adapter boom"), None]
    )

    # Should not raise
    await manager.apply_to(mock_registry)
    assert mock_registry.update_role_config.await_count == 2


# ── from_toml ────────────────────────────────────────────────────────────────


def test_from_toml_reads_llm_roles_section(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text(
        """
[llm_roles]
[llm_roles.extract]
model = "gpt-4"
temperature = 0.3

[llm_roles.query]
model = "gpt-3.5-turbo"
temperature = 0.7
"""
    )
    manager = LLMRoleConfigManager.from_toml(str(config_path))
    assert set(manager.configured_roles()) == {LLMRole.EXTRACT, LLMRole.QUERY}
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg.model_name == "gpt-4"
    assert cfg.temperature == pytest.approx(0.3)


def test_from_toml_missing_llm_roles(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text('app_name = "NoRoles"\n')
    manager = LLMRoleConfigManager.from_toml(str(config_path))
    assert manager.configured_roles() == []


def test_from_toml_nonexistent_path():
    manager = LLMRoleConfigManager.from_toml("/nonexistent/path.toml")
    assert manager.configured_roles() == []


# ── reload ───────────────────────────────────────────────────────────────────


def test_reload_rereads_toml(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text(
        """
[llm_roles]
[llm_roles.extract]
model = "gpt-4"
"""
    )
    manager = LLMRoleConfigManager.from_toml(str(config_path))
    assert LLMRole.EXTRACT in manager.configured_roles()

    # Modify the file
    config_path.write_text(
        """
[llm_roles]
[llm_roles.query]
model = "gpt-3.5-turbo"
"""
    )
    manager.reload()
    assert LLMRole.EXTRACT not in manager.configured_roles()
    assert LLMRole.QUERY in manager.configured_roles()


def test_reload_picks_up_new_env_vars(monkeypatch, tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text(
        """
[llm_roles]
[llm_roles.extract]
model = "gpt-4"
api_key = "sk-original"
"""
    )
    manager = LLMRoleConfigManager.from_toml(str(config_path))
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg.api_key == "sk-original"

    monkeypatch.setenv("AURORA_LLM_EXTRACT_API_KEY", "sk-rotated")
    manager.reload()
    cfg = manager.get_config(LLMRole.EXTRACT)
    assert cfg.api_key == "sk-rotated"


def test_reload_without_config_path_keeps_raw():
    """reload() with no config_path just re-resolves env vars."""
    manager = LLMRoleConfigManager({"extract": {"model": "gpt-4"}})
    manager.reload()  # should not raise
    assert LLMRole.EXTRACT in manager.configured_roles()


# ── Settings integration ─────────────────────────────────────────────────────


def test_settings_includes_llm_roles(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text(
        """
app_name = "Test"

[llm_roles]
[llm_roles.extract]
model = "gpt-4"
temperature = 0.3
"""
    )
    settings = Settings.from_toml(str(config_path))
    assert "extract" in settings.llm_roles
    assert settings.llm_roles["extract"]["model"] == "gpt-4"
    assert settings.llm_roles["extract"]["temperature"] == pytest.approx(0.3)


def test_settings_empty_llm_roles_by_default():
    settings = Settings()
    assert settings.llm_roles == {}


# ── LLMRole enum ─────────────────────────────────────────────────────────────


def test_llm_role_enum_values():
    assert LLMRole.EXTRACT.value == "extract"
    assert LLMRole.KEYWORDS.value == "keywords"
    assert LLMRole.QUERY.value == "query"
    assert LLMRole.VLM.value == "vlm"


def test_llm_role_is_str_enum():
    assert isinstance(LLMRole.EXTRACT, str)
    assert LLMRole.EXTRACT == "extract"
