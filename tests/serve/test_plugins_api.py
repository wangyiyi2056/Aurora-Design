from fastapi.testclient import TestClient

from chatbi_serve.server import create_app


def test_local_plugin_metadata_crud_and_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBI_METADATA_DB", str(tmp_path / "chatbi.db"))
    monkeypatch.setenv("CHATBI_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        created = client.post(
            "/api/v1/plugins",
            json={
                "name": "local-sql-tools",
                "description": "Local SQL helper plugin",
                "entrypoint": "plugins.sql_tools",
                "enabled": False,
                "config": {"safe_mode": True},
            },
        )
        assert created.status_code == 200
        plugin_id = created.json()["id"]
        assert created.json()["enabled"] is False

        toggled = client.post(f"/api/v1/plugins/{plugin_id}/enable", json={"enabled": True})
        assert toggled.status_code == 200
        assert toggled.json()["enabled"] is True

        detail = client.get(f"/api/v1/plugins/{plugin_id}")
        assert detail.status_code == 200
        assert detail.json()["name"] == "local-sql-tools"

        updated = client.put(
            f"/api/v1/plugins/{plugin_id}",
            json={"description": "Updated plugin", "config": {"safe_mode": False}},
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "Updated plugin"
        assert updated.json()["config"]["safe_mode"] is False

        disabled = client.post(f"/api/v1/plugins/{plugin_id}/disable")
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        enabled = client.post(f"/api/v1/plugins/{plugin_id}/enable", json={"enabled": True})
        assert enabled.status_code == 200

    with TestClient(create_app()) as client:
        plugins = client.get("/api/v1/plugins").json()["items"]
        assert plugins[0]["name"] == "local-sql-tools"
        assert plugins[0]["enabled"] is True

        deleted = client.delete(f"/api/v1/plugins/{plugin_id}")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
