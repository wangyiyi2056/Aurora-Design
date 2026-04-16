import pytest

from chatbi_core.model.registry import ModelRegistry


@pytest.fixture
def model_registry():
    return ModelRegistry()
