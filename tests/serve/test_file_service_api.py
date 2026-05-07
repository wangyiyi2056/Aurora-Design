from fastapi.testclient import TestClient

from aurora_serve.server import create_app


def test_uploaded_file_metadata_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/v1/files/upload",
            files={"file": ("sales.csv", b"category,value\nA,1\n", "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_id"]
        assert data["file_name"] == "sales.csv"
        assert data["content_type"] == "text/csv"
        assert data["size"] == 19
        assert data["purpose"] == "general"
        file_id = data["file_id"]

    with TestClient(create_app()) as client:
        list_resp = client.get("/api/v1/files")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["file_id"] == file_id
        assert items[0]["file_name"] == "sales.csv"

        detail_resp = client.get(f"/api/v1/files/{file_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["file_path"].endswith(".csv")

        delete_resp = client.delete(f"/api/v1/files/{file_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True
        assert client.get("/api/v1/files").json()["items"] == []
