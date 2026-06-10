"""Tests for LangfuseConfig and load_langfuse_config."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from aurora_ext.observability.config import (
    LangfuseConfig,
    _DEFAULT_FLUSH_INTERVAL,
    _DEFAULT_HOST,
    _DEFAULT_SAMPLE_RATE,
    load_langfuse_config,
)


# ── LangfuseConfig ───────────────────────────────────────────────────


class TestLangfuseConfig:
    """Tests for the LangfuseConfig dataclass."""

    def test_default_values(self):
        """Default config should be disabled with empty keys."""
        config = LangfuseConfig()
        assert config.enabled is False
        assert config.public_key == ""
        assert config.secret_key == ""
        assert config.host == _DEFAULT_HOST
        assert config.project_name == "Aurora RAG"
        assert config.release == ""
        assert config.debug is False
        assert config.flush_interval == _DEFAULT_FLUSH_INTERVAL
        assert config.sample_rate == _DEFAULT_SAMPLE_RATE
        assert config.default_tags == ()

    def test_is_configured_false_when_disabled(self):
        """is_configured should be False when enabled is False."""
        config = LangfuseConfig(
            enabled=False,
            public_key="pk-test",
            secret_key="sk-test",
        )
        assert config.is_configured is False

    def test_is_configured_false_when_missing_keys(self):
        """is_configured should be False when keys are missing."""
        config = LangfuseConfig(enabled=True)
        assert config.is_configured is False

    def test_is_configured_true_when_complete(self):
        """is_configured should be True when enabled + both keys."""
        config = LangfuseConfig(
            enabled=True,
            public_key="pk-test",
            secret_key="sk-test",
        )
        assert config.is_configured is True

    def test_to_dict_masks_keys(self):
        """to_dict should mask the secret key."""
        config = LangfuseConfig(
            enabled=True,
            public_key="pk-abcdefghijk",
            secret_key="sk-secret-value",
        )
        d = config.to_dict()
        assert d["public_key"] == "pk-abcde..."
        assert d["secret_key"] == "***"
        assert d["enabled"] is True

    def test_to_dict_empty_keys(self):
        """to_dict should handle empty keys gracefully."""
        config = LangfuseConfig()
        d = config.to_dict()
        assert d["public_key"] == ""
        assert d["secret_key"] == ""

    def test_frozen_dataclass(self):
        """Config should be immutable after construction."""
        config = LangfuseConfig()
        with pytest.raises(AttributeError):
            config.enabled = True  # type: ignore[misc]

    def test_default_tags_tuple(self):
        """default_tags should be a tuple."""
        config = LangfuseConfig(default_tags=("aurora", "rag"))
        assert config.default_tags == ("aurora", "rag")


# ── load_langfuse_config ─────────────────────────────────────────────


class TestLoadLangfuseConfig:
    """Tests for the load_langfuse_config function."""

    def test_load_with_no_sources(self):
        """Loading without any config source should return defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_langfuse_config()
        assert config.enabled is False
        assert config.host == _DEFAULT_HOST

    def test_load_from_env_vars(self):
        """Environment variables should populate the config."""
        env = {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-env",
            "LANGFUSE_SECRET_KEY": "sk-env",
            "LANGFUSE_HOST": "https://custom.langfuse.com",
            "LANGFUSE_DEBUG": "1",
            "LANGFUSE_PROJECT_NAME": "TestProject",
            "LANGFUSE_RELEASE": "v1.2.3",
            "LANGFUSE_FLUSH_INTERVAL": "2.5",
            "LANGFUSE_SAMPLE_RATE": "0.5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_langfuse_config()

        assert config.enabled is True
        assert config.public_key == "pk-env"
        assert config.secret_key == "sk-env"
        assert config.host == "https://custom.langfuse.com"
        assert config.debug is True
        assert config.project_name == "TestProject"
        assert config.release == "v1.2.3"
        assert config.flush_interval == 2.5
        assert config.sample_rate == 0.5

    def test_load_from_toml(self):
        """TOML section should populate config fields."""
        toml = {
            "langfuse": {
                "enabled": True,
                "public_key": "pk-toml",
                "secret_key": "sk-toml",
                "host": "https://toml.langfuse.com",
                "project_name": "TOML Project",
                "default_tags": ["tag1", "tag2"],
            }
        }
        with patch.dict(os.environ, {}, clear=True):
            config = load_langfuse_config(toml_config=toml)

        assert config.enabled is True
        assert config.public_key == "pk-toml"
        assert config.secret_key == "sk-toml"
        assert config.host == "https://toml.langfuse.com"
        assert config.project_name == "TOML Project"
        assert config.default_tags == ("tag1", "tag2")

    def test_env_overrides_toml(self):
        """Env vars should take priority over TOML."""
        toml = {
            "langfuse": {
                "enabled": False,
                "public_key": "pk-toml",
                "host": "https://toml.langfuse.com",
            }
        }
        env = {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-env",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_langfuse_config(toml_config=toml)

        assert config.enabled is True
        assert config.public_key == "pk-env"
        # host falls through to TOML since no env var set
        assert config.host == "https://toml.langfuse.com"

    def test_explicit_overrides_highest_priority(self):
        """Explicit overrides should beat both env and TOML."""
        toml = {"langfuse": {"public_key": "pk-toml"}}
        env = {"LANGFUSE_PUBLIC_KEY": "pk-env"}
        overrides = {"public_key": "pk-override"}

        with patch.dict(os.environ, env, clear=True):
            config = load_langfuse_config(
                toml_config=toml, overrides=overrides
            )

        assert config.public_key == "pk-override"

    def test_default_tags_from_string(self):
        """default_tags as comma-separated string should be parsed."""
        overrides = {"default_tags": "aurora, rag, test"}
        with patch.dict(os.environ, {}, clear=True):
            config = load_langfuse_config(overrides=overrides)

        assert config.default_tags == ("aurora", "rag", "test")

    def test_default_tags_from_list(self):
        """default_tags as list should be converted to tuple."""
        overrides = {"default_tags": ["aurora", "rag"]}
        with patch.dict(os.environ, {}, clear=True):
            config = load_langfuse_config(overrides=overrides)

        assert config.default_tags == ("aurora", "rag")

    def test_invalid_float_uses_default(self):
        """Invalid float env var should fall back to default."""
        env = {"LANGFUSE_FLUSH_INTERVAL": "not-a-number"}
        with patch.dict(os.environ, env, clear=True):
            config = load_langfuse_config()

        assert config.flush_interval == _DEFAULT_FLUSH_INTERVAL

    def test_bool_parsing_variants(self):
        """Various truthy strings should be accepted."""
        for val in ("1", "true", "True", "TRUE", "yes", "on"):
            env = {"LANGFUSE_ENABLED": val}
            with patch.dict(os.environ, env, clear=True):
                config = load_langfuse_config()
            assert config.enabled is True, f"Failed for {val!r}"

        for val in ("0", "false", "False", "no", "off", ""):
            env = {"LANGFUSE_ENABLED": val}
            with patch.dict(os.environ, env, clear=True):
                config = load_langfuse_config()
            assert config.enabled is False, f"Failed for {val!r}"
