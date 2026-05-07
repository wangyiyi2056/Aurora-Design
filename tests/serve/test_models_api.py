from fastapi.testclient import TestClient

from aurora_core.model.adapter.openai_adapter import OpenAILLM
from aurora_serve.chat.schema import ChatChoice, ChatMessage, ChatResponse
from aurora_serve.server import create_app


def test_model_config_crud_persists_and_masks_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

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


def test_deleted_model_config_is_removed_from_runtime_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": "runtime-model",
                "type": "llm",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-secret",
            },
        )
        model_id = create_resp.json()["id"]

        assert client.app.state.model_registry.get_llm("runtime-model")
        delete_resp = client.delete(f"/api/v1/models/{model_id}")
        assert delete_resp.status_code == 200

        try:
            client.app.state.model_registry.get_llm("runtime-model")
        except KeyError:
            pass
        else:
            raise AssertionError("deleted model remained registered at runtime")


def test_model_config_allows_local_openai_model_without_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": "local-openai",
                "type": "llm",
                "base_url": "http://127.0.0.1:8000/v1",
                "api_key": "",
            },
        )

        assert create_resp.status_code == 200
        assert create_resp.json()["api_key"] == ""
        assert client.app.state.model_registry.get_llm("local-openai")


def test_model_config_registers_daemon_model_without_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": "Local Codex",
                "type": "daemon",
                "base_url": "codex",
                "api_key": "",
            },
        )

        assert create_resp.status_code == 200
        llm = client.app.state.model_registry.get_llm("Local Codex")
        assert llm.config.model_type == "daemon"


def test_duplicate_model_name_returns_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

    with TestClient(create_app()) as client:
        payload = {
            "name": "duplicate-model",
            "type": "llm",
            "base_url": "http://127.0.0.1:8000/v1",
            "api_key": "",
        }
        assert client.post("/api/v1/models", json=payload).status_code == 200
        duplicate = client.post("/api/v1/models", json=payload)

        assert duplicate.status_code == 409
        assert "already exists" in duplicate.json()["detail"]


def test_kimi_coding_model_is_registered_with_openai_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

    with TestClient(create_app()) as client:
        create_resp = client.post(
            "/api/v1/models",
            json={
                "name": "kimi-k2.6",
                "type": "anthropic",
                "base_url": "https://api.kimi.com/coding/",
                "api_key": "sk-secret",
            },
        )

        assert create_resp.status_code == 200
        llm = client.app.state.model_registry.get_llm("kimi-k2.6")
        assert isinstance(llm, OpenAILLM)


def test_app_crud_and_publish_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

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


def test_app_run_reuses_chat_service_with_app_bindings(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))

    app = create_app()

    class FakeChatService:
        def __init__(self):
            self.last_req = None

        async def chat(self, req, session_id=None):
            self.last_req = req
            return ChatResponse(
                id="aurora-test",
                created=1,
                model=req.model or "unknown",
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content="app response"),
                        finish_reason="stop",
                    )
                ],
            )

    with TestClient(app) as client:
        fake_chat = FakeChatService()
        client.app.state.chat_service = fake_chat

        create_resp = client.post(
            "/api/v1/apps",
            json={
                "name": "Sales Analyst",
                "description": "Analyze sales data",
                "type": "chat",
                "model": "fake-model",
                "knowledge_ids": ["sales-kb"],
                "datasource_ids": ["sales-db"],
                "skill_names": ["database_schema"],
            },
        )
        app_id = create_resp.json()["id"]

        run_resp = client.post(
            f"/api/v1/apps/{app_id}/run",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

        assert run_resp.status_code == 200
        assert run_resp.json()["choices"][0]["message"]["content"] == "app response"
        assert fake_chat.last_req.model == "fake-model"
        assert fake_chat.last_req.ext_info["app_id"] == app_id
        assert fake_chat.last_req.ext_info["knowledge_ids"] == ["sales-kb"]
        assert fake_chat.last_req.ext_info["datasource_ids"] == ["sales-db"]
        assert fake_chat.last_req.ext_info["skill_names"] == ["database_schema"]
        assert fake_chat.last_req.ext_info["database_name"] == "sales-db"
