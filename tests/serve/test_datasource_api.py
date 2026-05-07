import pytest
from fastapi.testclient import TestClient

from chatbi_serve.server import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_datasource_lifecycle(client):
    # Create
    resp = client.post(
        "/api/v1/datasource",
        json={
            "config": {
                "name": "test-sqlite",
                "db_type": "sqlite",
                "database": ":memory:",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-sqlite"
    assert data["db_type"] == "sqlite"

    # List
    resp = client.get("/api/v1/datasource")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["name"] == "test-sqlite" for i in items)

    # Test connection
    resp = client.post("/api/v1/datasource/test-sqlite/test")
    assert resp.status_code == 200
    assert resp.json()["connected"] is True

    # Create table via query
    resp = client.post(
        "/api/v1/datasource/test-sqlite/query",
        json={"sql": "CREATE TABLE demo (id INTEGER PRIMARY KEY, val TEXT)"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Get tables
    resp = client.get("/api/v1/datasource/test-sqlite/tables")
    assert resp.status_code == 200
    assert "demo" in resp.json()["tables"]

    # Get schema
    resp = client.get("/api/v1/datasource/test-sqlite/schema/demo")
    assert resp.status_code == 200
    assert "id" in resp.json()["schema_ddl"]

    # Delete
    resp = client.delete("/api/v1/datasource/test-sqlite")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_datasource_detail_and_update(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"

    with TestClient(create_app()) as client:
        create = client.post(
            "/api/v1/datasource",
            json={
                "config": {
                    "name": "editable",
                    "db_type": "sqlite",
                    "database": str(first_db),
                }
            },
        )
        assert create.status_code == 200

        detail = client.get("/api/v1/datasource/editable")
        assert detail.status_code == 200
        assert detail.json()["config"]["database"] == str(first_db)

        update = client.put(
            "/api/v1/datasource/editable",
            json={
                "config": {
                    "name": "editable",
                    "db_type": "sqlite",
                    "database": str(second_db),
                }
            },
        )
        assert update.status_code == 200
        assert update.json()["name"] == "editable"

    with TestClient(create_app()) as client:
        detail = client.get("/api/v1/datasource/editable")
        assert detail.status_code == 200
        assert detail.json()["config"]["database"] == str(second_db)
