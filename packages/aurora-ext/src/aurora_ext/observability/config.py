"""Langfuse configuration — environment variables + TOML loading.

Configuration priority (highest → lowest):
  1. Explicit constructor arguments
  2. Environment variables (``LANGFUSE_*``)
  3. TOML config file (``[langfuse]`` section)
  4. Built-in defaults

The :class:`LangfuseConfig` dataclass is *frozen* to guarantee immutability
after construction.  Use :func:`load_langfuse_config` to build an instance
from the available configuration sources.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ── Environment variable names ───────────────────────────────────────

_ENV_PUBLIC_KEY = "LANGFUSE_PUBLIC_KEY"
_ENV_SECRET_KEY = "LANGFUSE_SECRET_KEY"
_ENV_HOST = "LANGFUSE_HOST"
_ENV_ENABLED = "LANGFUSE_ENABLED"
_ENV_DEBUG = "LANGFUSE_DEBUG"
_ENV_PROJECT_NAME = "LANGFUSE_PROJECT_NAME"
_ENV_RELEASE = "LANGFUSE_RELEASE"
_ENV_FLUSH_INTERVAL = "LANGFUSE_FLUSH_INTERVAL"
_ENV_SAMPLE_RATE = "LANGFUSE_SAMPLE_RATE"

# ── Defaults ─────────────────────────────────────────────────────────

_DEFAULT_HOST = "https://cloud.langfuse.com"
_DEFAULT_FLUSH_INTERVAL = 1.0  # seconds — keep short for async flush
_DEFAULT_SAMPLE_RATE = 1.0  # 100 %


@dataclass(frozen=True)
class LangfuseConfig:
    """Immutable Langfuse connection and tracing configuration.

    Attributes
    ----------
    enabled:
        Master toggle.  When ``False`` every tracing primitive becomes a
        transparent no-op with near-zero overhead.
    public_key:
        Langfuse project public key.
    secret_key:
        Langfuse project secret key.
    host:
        Langfuse server URL.  Defaults to the managed cloud instance.
    project_name:
        Human-readable project name attached to every trace.
    release:
        Release / version tag attached to every trace.
    debug:
        Enable Langfuse SDK debug logging.
    flush_interval:
        Background flush interval in seconds for the async upload queue.
    sample_rate:
        Fraction of traces to upload (``0.0``–``1.0``).  ``1.0`` uploads
        everything.
    default_tags:
        Tags applied to every trace created in this process.
    """

    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = _DEFAULT_HOST
    project_name: str = "Aurora RAG"
    release: str = ""
    debug: bool = False
    flush_interval: float = _DEFAULT_FLUSH_INTERVAL
    sample_rate: float = _DEFAULT_SAMPLE_RATE
    default_tags: tuple[str, ...] = ()

    # ── Derived properties ──────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when both keys and host are present.

        A config can be ``enabled=True`` but not *configured* if the
        required credentials are missing — tracing will stay disabled.
        """
        return self.enabled and bool(self.public_key) and bool(self.secret_key)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary (safe for logging)."""
        return {
            "enabled": self.enabled,
            "public_key": self.public_key[:8] + "..." if self.public_key else "",
            "secret_key": "***" if self.secret_key else "",
            "host": self.host,
            "project_name": self.project_name,
            "release": self.release,
            "debug": self.debug,
            "flush_interval": self.flush_interval,
            "sample_rate": self.sample_rate,
            "default_tags": list(self.default_tags),
        }


# ── Loading helpers ──────────────────────────────────────────────────


def _env_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    raw = os.environ.get(key, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    """Parse a float environment variable with fallback."""
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s: %r — using default %s", key, raw, default)
        return default


def load_langfuse_config(
    toml_config: dict[str, Any] | None = None,
    *,
    overrides: dict[str, Any] | None = None,
) -> LangfuseConfig:
    """Build a :class:`LangfuseConfig` from all available sources.

    Parameters
    ----------
    toml_config:
        The parsed TOML dictionary.  The ``[langfuse]`` section is used
        when present.
    overrides:
        Explicit key-value overrides applied last (highest priority).
    """
    section: dict[str, Any] = {}
    if toml_config:
        section = dict(toml_config.get("langfuse", {}))

    ov = overrides or {}

    def _get(key: str, env_key: str = "", default: Any = None) -> Any:
        """Resolve a config value: overrides → env → toml → default."""
        if key in ov:
            return ov[key]
        if env_key:
            raw = os.environ.get(env_key, "")
            if raw:
                return raw
        if key in section:
            return section[key]
        return default

    # Parse default_tags as a tuple regardless of source type
    raw_tags = _get("default_tags", default=())
    if isinstance(raw_tags, str):
        raw_tags = tuple(t.strip() for t in raw_tags.split(",") if t.strip())
    elif isinstance(raw_tags, list):
        raw_tags = tuple(raw_tags)

    return LangfuseConfig(
        enabled=_env_bool(_ENV_ENABLED, _get("enabled", default=False)),
        public_key=_get("public_key", _ENV_PUBLIC_KEY, ""),
        secret_key=_get("secret_key", _ENV_SECRET_KEY, ""),
        host=_get("host", _ENV_HOST, _DEFAULT_HOST),
        project_name=_get("project_name", _ENV_PROJECT_NAME, "Aurora RAG"),
        release=_get("release", _ENV_RELEASE, ""),
        debug=_env_bool(_ENV_DEBUG, _get("debug", default=False)),
        flush_interval=_env_float(
            _ENV_FLUSH_INTERVAL, _get("flush_interval", default=_DEFAULT_FLUSH_INTERVAL)
        ),
        sample_rate=_env_float(
            _ENV_SAMPLE_RATE, _get("sample_rate", default=_DEFAULT_SAMPLE_RATE)
        ),
        default_tags=raw_tags,
    )
