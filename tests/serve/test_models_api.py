from fastapi.testclient import TestClient

from chatbi_serve.server import create_app


def test_model_config_crud_persists_and_masks_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": "gpt-4o-mini",
                "type": "llm",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-secret",
                "is_default": True,
            },
        )
        assert create_resp.status_code == 200
        model_id = create_resp.json()["id"]

        list_resp = client.get("/api/v1/models")
        assert list_resp.status_code == 200
        item = list_resp.json()["items"][0]
        assert item["name"] == "gpt-4o-mini"
        assert item["api_key"] != "sk-secret"
        assert item["is_default"] is True

        update_resp = client.put(
            f"/api/v1/models/{model_id}",
            json={"name": "gpt-4o", "is_default": True},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "gpt-4o"

    with TestClient(create_app()) as client:
        persisted = client.get("/api/v1/models").json()["items"]
        assert [item["name"] for item in persisted] == ["gpt-4o"]

        delete_resp = client.delete(f"/api/v1/models/{model_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True


def test_app_crud_and_publish_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/apps",
            json={
                "name": "Data Analyst",
                "description": "Analyze sales data",
                "type": "chat",
                "model": "gpt-4o-mini",
                "knowledge_ids": ["sales-kb"],
                "datasource_ids": ["sales-db"],
                "skill_names": ["database_schema"],
            },
        )
        assert create_resp.status_code == 200
        app_id = create_resp.json()["id"]
        assert create_resp.json()["published"] is False

        publish_resp = client.post(f"/api/v1/apps/{app_id}/publish", json={"published": True})
        assert publish_resp.status_code == 200
        assert publish_resp.json()["published"] is True

    with TestClient(create_app()) as client:
        apps = client.get("/api/v1/apps").json()["items"]
        assert len(apps) == 1
        assert apps[0]["name"] == "Data Analyst"
        assert apps[0]["published"] is True
