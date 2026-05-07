from fastapi.testclient import TestClient

from aurora_serve.server import create_app


def test_evaluation_feedback_trace_and_user_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        dataset = client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "sales-eval", "description": "Sales benchmark", "data": [{"q": "hi"}]},
        )
        assert dataset.status_code == 200
        dataset_id = dataset.json()["id"]

        task = client.post(
            "/api/v1/evaluation/tasks",
            json={"name": "sales-task", "model": "gpt-4o-mini", "dataset_id": dataset_id},
        )
        assert task.status_code == 200
        assert client.get("/api/v1/evaluation/tasks").json()["items"][0]["status"] == "pending"

        feedback = client.post(
            "/api/v1/feedback",
            json={"target_type": "chat", "target_id": "session-1", "rating": 1, "comment": "good"},
        )
        assert feedback.status_code == 200
        assert client.get("/api/v1/feedback").json()["items"][0]["comment"] == "good"

        trace = client.post(
            "/api/v1/traces",
            json={"name": "chat.completion", "span_type": "llm", "metadata": {"model": "fake"}},
        )
        assert trace.status_code == 200
        assert client.get("/api/v1/traces").json()["items"][0]["name"] == "chat.completion"

        user = client.post(
            "/api/v1/users",
            json={"username": "owner", "display_name": "Owner", "role": "admin", "enabled": True},
        )
        assert user.status_code == 200
        assert client.get("/api/v1/users").json()["items"][0]["username"] == "owner"


def test_platform_modules_support_detail_update_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        dataset = client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "sales-eval", "description": "Sales benchmark", "data": [{"q": "hi"}]},
        ).json()
        task = client.post(
            "/api/v1/evaluation/tasks",
            json={"name": "sales-task", "model": "gpt-4o-mini", "dataset_id": dataset["id"]},
        ).json()
        feedback = client.post(
            "/api/v1/feedback",
            json={"target_type": "chat", "target_id": "session-1", "rating": 1, "comment": "good"},
        ).json()
        trace = client.post(
            "/api/v1/traces",
            json={"name": "chat.completion", "span_type": "llm", "metadata": {"model": "fake"}},
        ).json()
        user = client.post(
            "/api/v1/users",
            json={"username": "owner", "display_name": "Owner", "role": "admin", "enabled": True},
        ).json()

        assert client.get(f"/api/v1/evaluation/datasets/{dataset['id']}").json()["name"] == "sales-eval"
        assert client.put(
            f"/api/v1/evaluation/datasets/{dataset['id']}",
            json={"description": "Updated benchmark"},
        ).json()["description"] == "Updated benchmark"
        assert client.put(
            f"/api/v1/evaluation/tasks/{task['id']}",
            json={"status": "completed", "result": {"score": 0.9}},
        ).json()["result"]["score"] == 0.9
        assert client.put(
            f"/api/v1/feedback/{feedback['id']}",
            json={"rating": -1, "comment": "needs work"},
        ).json()["comment"] == "needs work"
        assert client.put(
            f"/api/v1/traces/{trace['id']}",
            json={"metadata": {"model": "fake", "tokens": 3}},
        ).json()["metadata"]["tokens"] == 3
        assert client.put(
            f"/api/v1/users/{user['id']}",
            json={"enabled": False, "role": "viewer"},
        ).json()["enabled"] is False

        assert client.delete(f"/api/v1/evaluation/tasks/{task['id']}").status_code == 200
        assert client.delete(f"/api/v1/evaluation/datasets/{dataset['id']}").status_code == 200
        assert client.delete(f"/api/v1/feedback/{feedback['id']}").status_code == 200
        assert client.delete(f"/api/v1/traces/{trace['id']}").status_code == 200
        assert client.delete(f"/api/v1/users/{user['id']}").status_code == 200

        assert client.get(f"/api/v1/evaluation/tasks/{task['id']}").status_code == 404
        assert client.get(f"/api/v1/users/{user['id']}").status_code == 404
