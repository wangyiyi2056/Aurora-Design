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


def test_knowledge_upload_persists_chunking_options(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))
    doc_path = tmp_path / "chunked.txt"
    doc_path.write_text("A" * 160, encoding="utf-8")

    with TestClient(create_app()) as client:
        client.app.state.model_registry.register_embeddings("fake", FakeEmbeddings())
        with doc_path.open("rb") as f:
            resp = client.post(
                "/api/v1/knowledge/upload"
                "?name=chunked&chunk_strategy=fixed&chunk_size=64&chunk_overlap=16",
                files={"file": ("chunked.txt", f, "text/plain")},
            )
        assert resp.status_code == 200
        assert resp.json()["chunk_strategy"] == "fixed"
        assert resp.json()["chunk_size"] == 64
        assert resp.json()["chunk_overlap"] == 16

    with TestClient(create_app()) as client:
        detail = client.get("/api/v1/knowledge/chunked")
        assert detail.status_code == 200
        assert detail.json()["chunk_strategy"] == "fixed"
        assert detail.json()["chunk_size"] == 64
        assert detail.json()["chunk_overlap"] == 16


def test_knowledge_documents_and_delete_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("alpha beta gamma", encoding="utf-8")

    with TestClient(create_app()) as client:
        client.app.state.model_registry.register_embeddings("fake", FakeEmbeddings())
        with doc_path.open("rb") as f:
            upload = client.post(
                "/api/v1/knowledge/upload?name=docs",
                files={"file": ("doc.txt", f, "text/plain")},
            )
        assert upload.status_code == 200

        docs = client.get("/api/v1/knowledge/docs/documents")
        assert docs.status_code == 200
        items = docs.json()["items"]
        assert len(items) == 1
        assert items[0]["file_name"] == "doc.txt"
        doc_id = items[0]["id"]

        query = client.post("/api/v1/knowledge/docs/query?query=alpha&top_k=1")
        assert query.status_code == 200
        assert len(query.json()["results"]) <= 1

        delete_doc = client.delete(f"/api/v1/knowledge/docs/documents/{doc_id}")
        assert delete_doc.status_code == 200
        assert delete_doc.json()["success"] is True
        assert client.get("/api/v1/knowledge/docs/documents").json()["items"] == []

        delete_kb = client.delete("/api/v1/knowledge/docs")
        assert delete_kb.status_code == 200
        assert delete_kb.json()["success"] is True
        assert client.get("/api/v1/knowledge").json() == []
