"""Tests for the Ollama compatibility layer.

Covers:
- Request/response mapping (mapper)
- Configuration loading
- Chat API (streaming + non-streaming)
- Generate API (streaming + non-streaming)
- Model management APIs (/api/tags, /api/show, /api/version, /api/ps)
- Open WebUI passthrough detection
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from aurora_serve.ollama_compat.config import (
    OllamaCompatConfig,
    _build_config_from_env,
    load_ollama_config,
    set_config,
)
from aurora_serve.ollama_compat.mapper import (
    build_conversation_history,
    count_tokens,
    inject_system_into_history,
    is_openwebui_passthrough,
    parse_mode_and_query,
)
from aurora_serve.ollama_compat.models import (
    OllamaChatRequest,
    OllamaChatResponse,
    OllamaGenerateRequest,
    OllamaMessage,
    OllamaModelInfo,
    OllamaShowRequest,
    OllamaTagsResponse,
)


# ═══════════════════════════════════════════════════════════════════
# Mapper Tests
# ═══════════════════════════════════════════════════════════════════


class TestParseModeAndQuery:
    """Test mode prefix parsing from message content."""

    def test_no_prefix_defaults_to_mix(self):
        mode, query = parse_mode_and_query("Hello, world!")
        assert mode == "mix"
        assert query == "Hello, world!"

    def test_local_prefix(self):
        mode, query = parse_mode_and_query("/local What is AI?")
        assert mode == "local"
        assert query == "What is AI?"

    def test_global_prefix(self):
        mode, query = parse_mode_and_query("/global Summarize the document")
        assert mode == "global"
        assert query == "Summarize the document"

    def test_hybrid_prefix(self):
        mode, query = parse_mode_and_query("/hybrid Find references")
        assert mode == "hybrid"
        assert query == "Find references"

    def test_naive_prefix(self):
        mode, query = parse_mode_and_query("/naive Simple search")
        assert mode == "naive"
        assert query == "Simple search"

    def test_bypass_prefix(self):
        mode, query = parse_mode_and_query("/bypass Just chat with me")
        assert mode == "bypass"
        assert query == "Just chat with me"

    def test_mix_prefix(self):
        mode, query = parse_mode_and_query("/mix Complex question")
        assert mode == "mix"
        assert query == "Complex question"

    def test_context_prefix_maps_to_mix(self):
        mode, query = parse_mode_and_query("/context Tell me more")
        assert mode == "mix"
        assert query == "Tell me more"

    def test_localcontext_prefix(self):
        mode, query = parse_mode_and_query("/localcontext Detail please")
        assert mode == "local"
        assert query == "Detail please"

    def test_longest_prefix_wins(self):
        """``/localcontext`` should match before ``/local``."""
        mode, query = parse_mode_and_query("/localcontext query here")
        assert mode == "local"
        assert query == "query here"

    def test_whitespace_handling(self):
        mode, query = parse_mode_and_query("  /hybrid   spaced query  ")
        assert mode == "hybrid"
        assert query == "spaced query"

    def test_empty_after_prefix(self):
        mode, query = parse_mode_and_query("/local")
        assert mode == "local"
        assert query == ""

    def test_unknown_prefix_treated_as_query(self):
        mode, query = parse_mode_and_query("/unknown What is this?")
        assert mode == "mix"
        assert query == "/unknown What is this?"


class TestOpenWebUIPassthrough:
    """Test OpenWebUI chat_history detection."""

    def test_detects_passthrough_marker(self):
        content = "Some text\n<chat_history>\nUSER: Hello\nASSISTANT: Hi"
        assert is_openwebui_passthrough(content) is True

    def test_normal_content_not_passthrough(self):
        assert is_openwebui_passthrough("Hello, how are you?") is False

    def test_partial_marker_not_detected(self):
        assert is_openwebui_passthrough("<chat_history>\nUSER:") is False

    def test_marker_must_have_newline_prefix(self):
        assert is_openwebui_passthrough("X\n<chat_history>\nUSER: hi") is True
        assert is_openwebui_passthrough("X<chat_history>\nUSER: hi") is False


class TestBuildConversationHistory:
    """Test conversation history construction from OllamaMessage lists."""

    def test_empty_messages(self):
        assert build_conversation_history([]) == []

    def test_single_message_excluded(self):
        msgs = [OllamaMessage(role="user", content="Hello")]
        assert build_conversation_history(msgs) == []

    def test_multiple_messages_last_excluded(self):
        msgs = [
            OllamaMessage(role="user", content="Hi"),
            OllamaMessage(role="assistant", content="Hello!"),
            OllamaMessage(role="user", content="How are you?"),
        ]
        history = build_conversation_history(msgs)
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hi"}
        assert history[1] == {"role": "assistant", "content": "Hello!"}

    def test_system_message_included(self):
        msgs = [
            OllamaMessage(role="system", content="You are helpful"),
            OllamaMessage(role="user", content="Hi"),
        ]
        history = build_conversation_history(msgs)
        assert len(history) == 1
        assert history[0] == {"role": "system", "content": "You are helpful"}


class TestCountTokens:
    """Test token counting heuristic."""

    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_nonempty_returns_positive(self):
        assert count_tokens("Hello") > 0

    def test_longer_text_more_tokens(self):
        short = count_tokens("Hi")
        long = count_tokens("This is a much longer sentence with many words")
        assert long > short


class TestInjectSystemIntoHistory:
    """Test system prompt injection into conversation history."""

    def test_no_system_prompt(self):
        history = [{"role": "user", "content": "Hi"}]
        result = inject_system_into_history(history, None)
        assert result == history

    def test_empty_system_prompt(self):
        history = [{"role": "user", "content": "Hi"}]
        result = inject_system_into_history(history, "")
        assert result == history

    def test_system_prepended(self):
        history = [{"role": "user", "content": "Hi"}]
        result = inject_system_into_history(history, "Be helpful")
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "Be helpful"}
        assert result[1] == {"role": "user", "content": "Hi"}

    def test_system_not_duplicated(self):
        history = [
            {"role": "system", "content": "Existing"},
            {"role": "user", "content": "Hi"},
        ]
        result = inject_system_into_history(history, "New system")
        assert len(result) == 2
        assert result[0]["content"] == "Existing"

    def test_does_not_mutate_input(self):
        history = [{"role": "user", "content": "Hi"}]
        original_len = len(history)
        inject_system_into_history(history, "System")
        assert len(history) == original_len


# ═══════════════════════════════════════════════════════════════════
# Configuration Tests
# ═══════════════════════════════════════════════════════════════════


class TestOllamaCompatConfig:
    """Test immutable configuration object."""

    def test_default_values(self):
        cfg = OllamaCompatConfig()
        assert cfg.enabled is True
        assert cfg.default_model == "aurora"
        assert cfg.default_tag == "latest"
        assert cfg.default_kb == "default"
        assert cfg.model_mapping == {}

    def test_full_model_name(self):
        cfg = OllamaCompatConfig(default_model="mymodel", default_tag="v2")
        assert cfg.full_model_name == "mymodel:v2"

    def test_resolve_kb_mapped(self):
        cfg = OllamaCompatConfig(
            model_mapping={"aurora-code": "code_kb"},
            default_kb="default",
        )
        assert cfg.resolve_kb("aurora-code") == "code_kb"

    def test_resolve_kb_strips_tag(self):
        cfg = OllamaCompatConfig(
            model_mapping={"aurora": "my_kb"},
            default_kb="default",
        )
        assert cfg.resolve_kb("aurora:latest") == "my_kb"

    def test_resolve_kb_fallback(self):
        cfg = OllamaCompatConfig(default_kb="fallback_kb")
        assert cfg.resolve_kb("unknown-model") == "fallback_kb"

    def test_list_models_includes_default(self):
        cfg = OllamaCompatConfig(
            default_model="aurora",
            model_mapping={"aurora-code": "code_kb"},
        )
        names = cfg.list_models()
        assert "aurora" in names
        assert "aurora-code" in names

    def test_immutable(self):
        cfg = OllamaCompatConfig()
        with pytest.raises(AttributeError):
            cfg.enabled = False  # type: ignore[misc]


class TestConfigLoading:
    """Test configuration loading from TOML and env vars."""

    def test_build_from_env_defaults(self):
        cfg = _build_config_from_env({})
        assert cfg.enabled is True
        assert cfg.default_kb == "default" or cfg.default_kb == os.getenv("OLLAMA_DEFAULT_KB", "default")

    def test_build_from_env_toml_section(self):
        cfg = _build_config_from_env({
            "enabled": False,
            "default_model": "mymodel",
            "default_tag": "v1",
            "default_kb": "my_kb",
            "model_mapping": {"model-a": "kb_a"},
        })
        assert cfg.enabled is False
        assert cfg.default_model == "mymodel"
        assert cfg.default_tag == "v1"
        assert cfg.default_kb == "my_kb"
        assert cfg.model_mapping == {"model-a": "kb_a"}

    def test_load_nonexistent_path(self, tmp_path):
        cfg = load_ollama_config(tmp_path / "nonexistent.toml")
        # Should fall back to defaults without error
        assert cfg.enabled is True

    def test_load_valid_toml(self, tmp_path):
        toml_content = """\
[ollama_compat]
enabled = true
default_model = "test-model"
default_tag = "beta"
default_kb = "test_kb"

[ollama_compat.model_mapping]
"test-model" = "test_kb"
"code-model" = "code_kb"
"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(toml_content)
        cfg = load_ollama_config(toml_file)
        assert cfg.default_model == "test-model"
        assert cfg.default_tag == "beta"
        assert cfg.default_kb == "test_kb"
        assert cfg.model_mapping["code-model"] == "code_kb"


# ═══════════════════════════════════════════════════════════════════
# Model (Pydantic) Tests
# ═══════════════════════════════════════════════════════════════════


class TestOllamaModels:
    """Test Pydantic request/response models."""

    def test_chat_request_defaults(self):
        req = OllamaChatRequest(
            messages=[OllamaMessage(role="user", content="Hello")]
        )
        assert req.model == "aurora"
        assert req.stream is True
        assert req.options == {}
        assert req.system is None

    def test_chat_request_immutable(self):
        req = OllamaChatRequest(
            messages=[OllamaMessage(role="user", content="Hello")]
        )
        with pytest.raises(Exception):
            req.model = "changed"  # type: ignore[misc]

    def test_generate_request(self):
        req = OllamaGenerateRequest(prompt="Tell me a story")
        assert req.model == "aurora"
        assert req.stream is False
        assert req.prompt == "Tell me a story"

    def test_show_request(self):
        req = OllamaShowRequest(name="aurora:latest")
        assert req.name == "aurora:latest"

    def test_tags_response(self):
        resp = OllamaTagsResponse(models=[])
        assert resp.models == []

    def test_chat_response(self):
        resp = OllamaChatResponse(
            model="aurora:latest",
            created_at="2024-01-01T00:00:00Z",
            message=OllamaMessage(role="assistant", content="Hi!"),
            done=True,
            total_duration=1000000,
            prompt_eval_count=10,
            eval_count=5,
        )
        assert resp.done is True
        assert resp.message.content == "Hi!"


# ═══════════════════════════════════════════════════════════════════
# Integration Tests (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_service():
    """Create a mock KnowledgeV2Service."""
    svc = AsyncMock()

    # Non-streaming query
    svc.query = AsyncMock(return_value={
        "response": "Aurora is an agentic AI data platform.",
        "entities": [],
        "relationships": [],
        "chunks": [],
        "references": [],
    })

    # Non-streaming generate
    svc.llm_generate = AsyncMock(return_value={
        "response": "Once upon a time...",
    })

    return svc


@pytest.fixture
def test_config():
    """Create a test configuration."""
    cfg = OllamaCompatConfig(
        enabled=True,
        default_model="aurora",
        default_tag="latest",
        default_kb="default",
        model_mapping={
            "aurora": "default",
            "aurora-code": "code_kb",
        },
    )
    set_config(cfg)
    return cfg


@pytest.fixture
def client(mock_service, test_config):
    """Create a FastAPI TestClient with mock dependencies."""
    from fastapi import FastAPI

    from aurora_serve.ollama_compat.routes import router

    app = FastAPI()
    app.include_router(router)

    # Wire up the mock service via system_app mock
    system_app = MagicMock()
    system_app.get_component = MagicMock(return_value=mock_service)
    app.state.system_app = system_app

    return TestClient(app)


class TestOllamaVersion:
    def test_returns_version(self, client):
        resp = client.get("/api/version")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.9.3"


class TestOllamaTags:
    def test_returns_model_list(self, client, test_config):
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 1

        names = [m["name"] for m in data["models"]]
        assert "aurora:latest" in names

    def test_model_has_required_fields(self, client):
        resp = client.get("/api/tags")
        model = resp.json()["models"][0]
        assert "name" in model
        assert "model" in model
        assert "size" in model
        assert "digest" in model
        assert "details" in model


class TestOllamaShow:
    def test_show_known_model(self, client):
        resp = client.post("/api/show", json={"name": "aurora"})
        assert resp.status_code == 200
        data = resp.json()
        assert "license" in data
        assert "modelfile" in data
        assert "parameters" in data
        assert "aurora" in data["modelfile"] or "default" in data["modelfile"]

    def test_show_with_tag(self, client):
        resp = client.post("/api/show", json={"name": "aurora:latest"})
        assert resp.status_code == 200

    def test_show_unknown_model_404(self, client):
        resp = client.post("/api/show", json={"name": "nonexistent-model"})
        assert resp.status_code == 404


class TestOllamaRunningModels:
    def test_returns_running_models(self, client):
        resp = client.get("/api/ps")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 1


class TestOllamaChat:
    def test_non_streaming_chat(self, client, mock_service):
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [{"role": "user", "content": "What is Aurora?"}],
            "stream": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "aurora:latest"
        assert data["done"] is True
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert len(data["message"]["content"]) > 0

    def test_streaming_chat(self, client, mock_service):
        """Test streaming chat returns NDJSON with done=true at end."""
        # Set up mock to return a stream iterator
        async def fake_stream():
            yield "Hello "
            yield "world!"

        mock_service.query = AsyncMock(return_value={
            "stream_iterator": fake_stream(),
            "response": "",
        })

        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        })
        assert resp.status_code == 200

        lines = [
            json.loads(line)
            for line in resp.text.strip().split("\n")
            if line.strip()
        ]
        assert len(lines) >= 2
        # Last line should have done=True
        assert lines[-1]["done"] is True
        # Intermediate lines should have done=False
        for line in lines[:-1]:
            assert line["done"] is False
            assert "message" in line

    def test_chat_with_mode_prefix(self, client, mock_service):
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [{"role": "user", "content": "/local What is AI?"}],
            "stream": False,
        })
        assert resp.status_code == 200
        # Verify the service was called with mode="local"
        call_kwargs = mock_service.query.call_args.kwargs
        assert call_kwargs["mode"] == "local"
        assert call_kwargs["query"] == "What is AI?"

    def test_chat_with_conversation_history(self, client, mock_service):
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "How are you?"},
            ],
            "stream": False,
        })
        assert resp.status_code == 200
        call_kwargs = mock_service.query.call_args.kwargs
        assert len(call_kwargs["conversation_history"]) == 2

    def test_chat_empty_messages_rejected(self, client):
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [],
            "stream": False,
        })
        assert resp.status_code == 400

    def test_chat_model_mapping(self, client, mock_service):
        """Model name 'aurora-code' should map to 'code_kb'."""
        resp = client.post("/api/chat", json={
            "model": "aurora-code",
            "messages": [{"role": "user", "content": "Explain Python"}],
            "stream": False,
        })
        assert resp.status_code == 200
        call_kwargs = mock_service.query.call_args.kwargs
        assert call_kwargs["kb_name"] == "code_kb"

    def test_chat_system_prompt_injected(self, client, mock_service):
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "You are a helpful assistant",
            "stream": False,
        })
        assert resp.status_code == 200
        call_kwargs = mock_service.query.call_args.kwargs
        history = call_kwargs["conversation_history"]
        assert any(m["role"] == "system" for m in history)


class TestOllamaChatOpenWebUIPattern:
    """Simulate Open WebUI request patterns."""

    def test_openwebui_passthrough_bypasses_rag(self, client, mock_service):
        """When OpenWebUI sends chat_history pattern, mode should be bypass."""
        content = "Some context\n<chat_history>\nUSER: Hi\nASSISTANT: Hello"
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        })
        assert resp.status_code == 200
        call_kwargs = mock_service.query.call_args.kwargs
        assert call_kwargs["mode"] == "bypass"

    def test_openwebui_typical_request(self, client, mock_service):
        """Simulate a typical Open WebUI request with system prompt."""
        resp = client.post("/api/chat", json={
            "model": "aurora",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant.",
                },
                {"role": "user", "content": "What can you do?"},
            ],
            "stream": True,
            "options": {"temperature": 0.7},
        })
        assert resp.status_code == 200


class TestOllamaGenerate:
    def test_non_streaming_generate(self, client, mock_service):
        resp = client.post("/api/generate", json={
            "model": "aurora",
            "prompt": "Tell me a story",
            "stream": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "aurora:latest"
        assert data["done"] is True
        assert "response" in data

    def test_streaming_generate(self, client, mock_service):
        async def fake_stream():
            yield "Once "
            yield "upon "
            yield "a time..."

        mock_service.llm_generate = AsyncMock(return_value={
            "stream_iterator": fake_stream(),
        })

        resp = client.post("/api/generate", json={
            "model": "aurora",
            "prompt": "Tell me a story",
            "stream": True,
        })
        assert resp.status_code == 200

        lines = [
            json.loads(line)
            for line in resp.text.strip().split("\n")
            if line.strip()
        ]
        assert len(lines) >= 2
        assert lines[-1]["done"] is True

    def test_generate_with_system(self, client, mock_service):
        resp = client.post("/api/generate", json={
            "model": "aurora",
            "prompt": "Hello",
            "system": "You are a poet",
            "stream": False,
        })
        assert resp.status_code == 200
        call_kwargs = mock_service.llm_generate.call_args.kwargs
        assert call_kwargs["system"] == "You are a poet"
