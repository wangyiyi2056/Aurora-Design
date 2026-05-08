import pytest

from aurora_core.model.adapter.cli_adapter import LocalCliLLM
from aurora_core.model.local_cli import (
    ClaudeStreamParser,
    JsonEventStreamParser,
    build_agent_args,
    clamp_codex_reasoning,
    sanitize_custom_model,
)
from aurora_core.schema.message import Message
from aurora_core.schema.model import LLMConfig


def test_build_codex_args_uses_stdin_without_dash_sentinel():
    args = build_agent_args("codex", model="gpt-5-codex", reasoning="minimal", cwd="/tmp/work")

    assert args[:2] == ["exec", "--json"]
    assert "-C" in args
    assert "/tmp/work" in args
    assert "--model" in args
    assert "gpt-5-codex" in args
    assert "-" not in args


def test_build_claude_args_matches_open_design_partial_streaming(monkeypatch):
    monkeypatch.setattr(
        "aurora_core.model.local_cli._agent_capability",
        lambda agent, capability: agent.id == "claude" and capability == "partialMessages",
    )

    args = build_agent_args("claude")

    assert args[:3] == ["-p", "--output-format", "stream-json"]
    assert "--verbose" in args
    assert "--include-partial-messages" in args


def test_sanitize_custom_model_rejects_flag_injection():
    with pytest.raises(ValueError):
        sanitize_custom_model("--danger")
    with pytest.raises(ValueError):
        sanitize_custom_model("model with spaces")


def test_clamp_codex_reasoning_matches_late_gpt5_family():
    assert clamp_codex_reasoning("gpt-5.5", "minimal") == "low"
    assert clamp_codex_reasoning("gpt-5.1", "xhigh") == "high"
    assert clamp_codex_reasoning("gpt-5.1-codex-mini", "low") == "medium"


def test_claude_stream_parser_matches_open_design_tool_result_events():
    events = []
    parser = ClaudeStreamParser(events.append)

    parser.feed(
        '{"type":"user","message":{"content":[{"type":"tool_result",'
        '"tool_use_id":"tool-1","content":[{"type":"text","text":"README contents"}],'
        '"is_error":false}]}}\n'
    )

    assert events == [
        {
            "type": "tool_result",
            "toolUseId": "tool-1",
            "content": "README contents",
            "isError": False,
        }
    ]


def test_claude_stream_parser_emits_thinking_start_like_open_design():
    events = []
    parser = ClaudeStreamParser(events.append)

    parser.feed(
        '{"type":"stream_event","event":{"type":"content_block_start","index":0,'
        '"content_block":{"type":"thinking"}}}\n'
    )

    assert events == [{"type": "thinking_start"}]


def test_claude_stream_parser_preserves_final_thinking_block_like_open_design():
    events = []
    parser = ClaudeStreamParser(events.append)

    parser.feed(
        '{"type":"assistant","message":{"id":"msg-1","content":['
        '{"type":"thinking","thinking":"reading project"},'
        '{"type":"text","text":"done"}]}}\n'
    )

    assert events == [
        {"type": "thinking_delta", "delta": "reading project"},
        {"type": "text_delta", "delta": "done"},
    ]


def test_codex_json_event_parser_matches_open_design_command_and_message_events():
    events = []
    parser = JsonEventStreamParser("codex", events.append)

    parser.feed(
        '{"type":"item.started","item":{"id":"cmd-1","type":"command_execution",'
        '"command":"pwd"}}\n'
        '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution",'
        '"command":"pwd","aggregated_output":"/Users/wyl/Desktop/chatBI","exit_code":0}}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
    )

    assert events == [
        {
            "type": "tool_use",
            "id": "cmd-1",
            "name": "Bash",
            "input": {"command": "pwd"},
        },
        {
            "type": "tool_result",
            "toolUseId": "cmd-1",
            "content": "/Users/wyl/Desktop/chatBI",
            "isError": False,
        },
        {"type": "text_delta", "delta": "done"},
    ]


@pytest.mark.asyncio
async def test_local_cli_adapter_preserves_open_design_agent_events(monkeypatch):
    async def fake_run_agent_stream(*args, **kwargs):
        yield {"type": "status", "label": "running"}
        yield {"type": "thinking_start"}
        yield {"type": "thinking_delta", "delta": "reading project"}
        yield {
            "type": "tool_use",
            "id": "tool-1",
            "name": "Read",
            "input": {"filePath": "README.md"},
        }
        yield {
            "type": "tool_result",
            "toolUseId": "tool-1",
            "content": "README contents",
            "isError": False,
        }
        yield {"type": "text_delta", "delta": "done"}

    monkeypatch.setattr(
        "aurora_core.model.adapter.cli_adapter.run_agent_stream",
        fake_run_agent_stream,
    )

    llm = LocalCliLLM(LLMConfig(model_name="codex", model_type="cli", api_base="codex"))
    chunks = [chunk async for chunk in llm.achat_stream([Message(role="user", content="hi")])]

    assert chunks[0].extra == {"event_type": "status", "label": "running"}
    assert chunks[1].extra == {"event_type": "status", "label": "thinking"}
    assert chunks[2].is_reasoning is True
    assert chunks[2].text == "reading project"
    assert chunks[3].extra == {
        "event_type": "tool_use",
        "id": "tool-1",
        "name": "Read",
        "input": {"filePath": "README.md"},
    }
    assert chunks[4].extra == {
        "event_type": "tool_result",
        "toolUseId": "tool-1",
        "content": "README contents",
        "isError": False,
    }
    assert chunks[5].text == "done"
