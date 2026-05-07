import pytest

from aurora_core.model.local_cli import (
    build_agent_args,
    clamp_codex_reasoning,
    sanitize_custom_model,
)


def test_build_codex_args_uses_stdin_without_dash_sentinel():
    args = build_agent_args("codex", model="gpt-5-codex", reasoning="minimal", cwd="/tmp/work")

    assert args[:2] == ["exec", "--json"]
    assert "-C" in args
    assert "/tmp/work" in args
    assert "--model" in args
    assert "gpt-5-codex" in args
    assert "-" not in args


def test_sanitize_custom_model_rejects_flag_injection():
    with pytest.raises(ValueError):
        sanitize_custom_model("--danger")
    with pytest.raises(ValueError):
        sanitize_custom_model("model with spaces")


def test_clamp_codex_reasoning_matches_late_gpt5_family():
    assert clamp_codex_reasoning("gpt-5.5", "minimal") == "low"
    assert clamp_codex_reasoning("gpt-5.1", "xhigh") == "high"
    assert clamp_codex_reasoning("gpt-5.1-codex-mini", "low") == "medium"
