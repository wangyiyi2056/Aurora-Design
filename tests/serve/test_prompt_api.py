from fastapi.testclient import TestClient

from chatbi_serve.server import create_app


def test_prompt_template_crud_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        created = client.post(
            "/api/v1/prompts",
            json={
                "name": "sql-default",
                "category": "sql",
                "template": "Question: {{question}}\nSchema: {{schema}}",
                "variables": ["question", "schema"],
                "version": 1,
                "enabled": True,
            },
        )
        assert created.status_code == 200
        prompt_id = created.json()["id"]

        listed = client.get("/api/v1/prompts?category=sql")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["name"] == "sql-default"

        updated = client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"template": "SQL: {{question}}", "version": 2},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        rendered = client.post(
            f"/api/v1/prompts/{prompt_id}/render",
            json={"variables": {"question": "top sales"}},
        )
        assert rendered.status_code == 200
        assert rendered.json()["content"] == "SQL: top sales"

        missing = client.post(
            f"/api/v1/prompts/{prompt_id}/render",
            json={"variables": {}},
        )
        assert missing.status_code == 422

    with TestClient(create_app()) as client:
        persisted = client.get(f"/api/v1/prompts/{prompt_id}")
        assert persisted.status_code == 200
        assert persisted.json()["template"] == "SQL: {{question}}"

        deleted = client.delete(f"/api/v1/prompts/{prompt_id}")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
