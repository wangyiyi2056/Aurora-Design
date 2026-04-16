import pytest

from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.schema.message import Message
from chatbi_core.schema.model import LLMConfig


def test_openai_llm_init():
    config = LLMConfig(
        model_name="gpt-4o-mini",
        model_type="openai",
        api_key="test-key",
        api_base="https://test.example.com/v1",
    )
    llm = OpenAILLM(config)
    assert llm.config.model_name == "gpt-4o-mini"
    assert llm.client.api_key == "test-key"
    assert str(llm.client.base_url) == "https://test.example.com/v1/"


@pytest.mark.asyncio
async def test_openai_llm_achat_mock(monkeypatch):
    config = LLMConfig(model_name="gpt-4o-mini", model_type="openai", api_key="test")
    llm = OpenAILLM(config)

    class FakeChoice:
        def __init__(self):
            self.message = type("obj", (object,), {"content": "hello"})()
            self.finish_reason = "stop"

    class FakeUsage:
        def model_dump(self):
            return {"prompt_tokens": 1, "completion_tokens": 1}

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    async def fake_create(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    result = await llm.achat([Message(role="user", content="hi")])
    assert result.text == "hello"
    assert result.finish_reason == "stop"
    assert result.usage == {"prompt_tokens": 1, "completion_tokens": 1}
