from fastapi.testclient import TestClient

from chatbi_serve.server import create_app


def test_awel_flow_crud_and_run_history(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        operators = client.get("/api/v1/awel/operators")
        assert operators.status_code == 200
        assert any(item["name"] == "identity" for item in operators.json())

        created = client.post(
            "/api/v1/awel/flows",
            json={
                "name": "echo-flow",
                "description": "Echo input",
                "nodes": [{"id": "identity", "type": "identity"}],
                "edges": [],
                "variables": {"language": "zh"},
            },
        )
        assert created.status_code == 200
        flow_id = created.json()["id"]

        run = client.post(f"/api/v1/awel/flows/{flow_id}/run", json={"initial_input": "hello"})
        assert run.status_code == 200
        assert run.json()["output"] == "hello"
        assert run.json()["flow_id"] == flow_id

        runs = client.get(f"/api/v1/awel/flows/{flow_id}/runs")
        assert runs.status_code == 200
        assert len(runs.json()["items"]) == 1
        run_id = runs.json()["items"][0]["id"]

        detail = client.get(f"/api/v1/awel/flows/{flow_id}")
        assert detail.status_code == 200
        assert detail.json()["name"] == "echo-flow"

        updated = client.put(
            f"/api/v1/awel/flows/{flow_id}",
            json={"description": "Updated", "nodes": [{"id": "upper", "type": "uppercase"}]},
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "Updated"

        run_detail = client.get(f"/api/v1/awel/runs/{run_id}")
        assert run_detail.status_code == 200
        assert run_detail.json()["output"] == "hello"

    with TestClient(create_app()) as client:
        flows = client.get("/api/v1/awel/flows").json()["items"]
        assert flows[0]["description"] == "Updated"

        deleted = client.delete(f"/api/v1/awel/flows/{flow_id}")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
        assert client.get(f"/api/v1/awel/flows/{flow_id}").status_code == 404


def test_legacy_awel_run_still_works(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        resp = client.post("/api/v1/awel/run", json={"initial_input": "hello"})
        assert resp.status_code == 200
        assert resp.json()["output"] == "hello"
