import pytest

from chatbi_core.model.registry import ModelRegistry


@pytest.fixture(autouse=True)
def isolated_metadata_db(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))


@pytest.fixture
def model_registry():
    return ModelRegistry()
