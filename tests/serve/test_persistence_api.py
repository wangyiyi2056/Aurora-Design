from pathlib import Path

from fastapi.testclient import TestClient

from chatbi_core.schema.message import ModelOutput
from chatbi_serve.server import create_app


class FakeEmbeddings:
    async def aembed(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]


def test_datasource_configs_survive_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    sqlite_path = tmp_path / "source.db"

    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/v1/datasource",
            json={
                "config": {
                    "name": "sales",
                    "db_type": "sqlite",
                    "database": str(sqlite_path),
                }
            },
        )
        assert resp.status_code == 200

    with TestClient(create_app()) as client:
        items = client.get("/api/v1/datasource").json()["items"]
        assert any(item["name"] == "sales" and item["connected"] for item in items)


def test_knowledge_metadata_survives_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("ChatBI supports RAG and SQL.", encoding="utf-8")

    with TestClient(create_app()) as client:
        client.app.state.model_registry.register_embeddings("fake", FakeEmbeddings())
        with doc_path.open("rb") as f:
            resp = client.post(
                "/api/v1/knowledge/upload?name=docs",
                files={"file": ("doc.txt", f, "text/plain")},
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "docs"

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/knowledge").json() == ["docs"]
