import pytest

from chatbi_core.model.base import BaseLLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.chat.schema import ChatRequest, ChatMessage
from chatbi_serve.chat.service import ChatService


class FakeLLM(BaseLLM):
    async def achat(self, messages, **kwargs):
        return ModelOutput(text="fake response")

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text="fake")
        yield ModelOutput(text=" response")


@pytest.fixture
def service():
    registry = ModelRegistry()
    registry.register_llm("fake", FakeLLM(LLMConfig(model_name="fake", model_type="test")))
    return ChatService(registry)


@pytest.mark.asyncio
async def test_chat_service_chat(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
    )
    resp = await service.chat(req)
    assert resp.choices[0].message.content == "fake response"
    assert resp.model == "fake"


@pytest.mark.asyncio
async def test_chat_service_stream(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )
    chunks = []
    async for line in service.chat_stream(req):
        chunks.append(line)
    assert any("fake" in chunk for chunk in chunks)
    assert any("[DONE]" in chunk for chunk in chunks)
