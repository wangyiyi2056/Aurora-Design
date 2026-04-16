import pytest

from chatbi_core.model.base import BaseLLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig


class FakeLLM(BaseLLM):
    async def achat(self, messages, **kwargs):
        return ModelOutput(text="fake")

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text="fake")


def test_register_and_get_llm():
    registry = ModelRegistry()
    llm = FakeLLM(LLMConfig(model_name="fake", model_type="test"))
    registry.register_llm("fake", llm)
    assert registry.get_llm("fake") is llm
    assert registry.get_llm() is llm


def test_get_llm_not_found():
    registry = ModelRegistry()
    with pytest.raises(KeyError):
        registry.get_llm("missing")


def test_get_llm_empty():
    registry = ModelRegistry()
    with pytest.raises(RuntimeError):
        registry.get_llm()
