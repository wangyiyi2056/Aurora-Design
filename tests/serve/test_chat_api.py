import pytest
from fastapi.testclient import TestClient

from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.chat.service import ChatService
from chatbi_serve.server import create_app


@pytest.fixture
def client():
    app = create_app()
    # Override with fake service to avoid real LLM calls
    registry = ModelRegistry()

    class FakeLLM:
        config = LLMConfig(model_name="fake", model_type="test")

        async def achat(self, messages, **kwargs):
            from chatbi_core.schema.message import ModelOutput

            return ModelOutput(text="hello from fake")

        async def achat_stream(self, messages, **kwargs):
            from chatbi_core.schema.message import ModelOutput

            yield ModelOutput(text="hello")
            yield ModelOutput(text=" from fake")

    registry.register_llm("fake", FakeLLM())
    app.state.chat_service = ChatService(registry)
    return TestClient(app)


def test_chat_completions_non_stream(client):
    resp = client.post(
        "/api/v1/chat/completions",
        json={"model": "fake", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "hello from fake"


def test_chat_completions_stream(client):
    resp = client.post(
        "/api/v1/chat/completions",
        json={
            "model": "fake",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    body = resp.read().decode()
    assert "data:" in body
    assert "[DONE]" in body
