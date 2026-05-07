import pytest

from aurora_core.model.registry import ModelRegistry


@pytest.fixture(autouse=True)
def isolated_metadata_db(monkeypatch, tmp_path):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))


@pytest.fixture
def model_registry():
    return ModelRegistry()
