from fastapi.testclient import TestClient

from aurora_serve.server import create_app


def test_sessions_use_storage_dir_and_support_title_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        create_resp = client.post("/api/v1/chat/sessions")
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]
        assert create_resp.json()["session"]["id"] == session_id

        list_resp = client.get("/api/v1/chat/sessions")
        assert list_resp.status_code == 200
        assert any(item["id"] == session_id for item in list_resp.json()["sessions"])

        session_meta = tmp_path / "storage" / "sessions" / f"{session_id}.meta.json"
        assert session_meta.exists()

        title_resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}/title",
            json={"title": "Sales analysis"},
        )
        assert title_resp.status_code == 200
        assert title_resp.json()["session"]["title"] == "Sales analysis"

    with TestClient(create_app()) as client:
        loaded = client.get(f"/api/v1/chat/sessions/{session_id}")
        assert loaded.status_code == 200
        assert loaded.json()["session"]["title"] == "Sales analysis"


def test_session_messages_persist_context_attachments(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        create_resp = client.post("/api/v1/chat/sessions")
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        upsert_resp = client.put(
            f"/api/v1/chat/sessions/{session_id}/messages/user-1",
            json={
                "type": "user",
                "role": "user",
                "content": "介绍数据源",
                "context_attachments": [
                    {"kind": "datasource", "name": "sales-db"},
                    {"kind": "design_skill", "id": "dashboard", "name": "dashboard"},
                ],
            },
        )
        assert upsert_resp.status_code == 200

    with TestClient(create_app()) as client:
        loaded = client.get(f"/api/v1/chat/sessions/{session_id}")
        assert loaded.status_code == 200
        message = loaded.json()["messages"][0]
        assert message["context_attachments"] == [
            {"kind": "datasource", "name": "sales-db"},
            {"kind": "design_skill", "id": "dashboard", "name": "dashboard"},
        ]
