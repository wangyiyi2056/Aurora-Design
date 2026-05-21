from fastapi.testclient import TestClient

from aurora_serve.server import create_app


def test_workspace_text_file_lifecycle_and_nested_assets(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        workspace_id = "session-123"
        html = '<!doctype html><html><body><img src="../assets/logo.png"></body></html>'

        write_resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/files",
            json={
                "name": "reports/index.html",
                "content": html,
                "encoding": "utf8",
            },
        )
        assert write_resp.status_code == 200
        written = write_resp.json()["file"]
        assert written["name"] == "reports/index.html"
        assert written["kind"] == "html"
        assert written["mime"] == "text/html"

        upload_resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/upload",
            data={"base_dir": "assets"},
            files={"files": ("logo.png", b"fake-png", "image/png")},
        )
        assert upload_resp.status_code == 200
        uploaded = upload_resp.json()["files"][0]
        assert uploaded["name"] == "assets/logo.png"
        assert uploaded["kind"] == "image"

        list_resp = client.get(f"/api/v1/workspaces/{workspace_id}/files")
        assert list_resp.status_code == 200
        files = {item["name"]: item for item in list_resp.json()["files"]}
        assert set(files) == {"assets/logo.png", "reports/index.html"}
        assert files["reports/index.html"]["size"] == len(html.encode())

        raw_html = client.get(f"/api/v1/workspaces/{workspace_id}/raw/reports/index.html")
        assert raw_html.status_code == 200
        assert raw_html.text == html
        assert raw_html.headers["content-type"].startswith("text/html")

        raw_asset = client.get(f"/api/v1/workspaces/{workspace_id}/raw/assets/logo.png")
        assert raw_asset.status_code == 200
        assert raw_asset.content == b"fake-png"
        assert raw_asset.headers["content-type"].startswith("image/png")

        archive = client.get(f"/api/v1/workspaces/{workspace_id}/archive")
        assert archive.status_code == 200
        assert archive.headers["content-type"].startswith("application/zip")
        assert archive.content.startswith(b"PK")

        rename_resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/files/rename",
            json={"from": "reports/index.html", "to": "reports/report.html"},
        )
        assert rename_resp.status_code == 200
        assert rename_resp.json()["oldName"] == "reports/index.html"
        assert rename_resp.json()["newName"] == "reports/report.html"
        assert rename_resp.json()["file"]["name"] == "reports/report.html"

        deleted = client.delete(f"/api/v1/workspaces/{workspace_id}/raw/reports/report.html")
        assert deleted.status_code == 200
        assert deleted.json() == {"ok": True}

        final_files = client.get(f"/api/v1/workspaces/{workspace_id}/files").json()["files"]
        assert [item["name"] for item in final_files] == ["assets/logo.png"]


def test_workspace_rejects_unsafe_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        workspace_id = "safe-session"

        traversal_write = client.post(
            f"/api/v1/workspaces/{workspace_id}/files",
            json={"name": "../escape.html", "content": "nope"},
        )
        assert traversal_write.status_code == 400

        absolute_write = client.post(
            f"/api/v1/workspaces/{workspace_id}/files",
            json={"name": "/tmp/escape.html", "content": "nope"},
        )
        assert absolute_write.status_code == 400

        traversal_read = client.get(f"/api/v1/workspaces/{workspace_id}/raw/%2e%2e/escape.html")
        assert traversal_read.status_code == 400

        traversal_upload = client.post(
            f"/api/v1/workspaces/{workspace_id}/upload",
            data={"base_dir": "../escape"},
            files={"files": ("logo.png", b"fake-png", "image/png")},
        )
        assert traversal_upload.status_code == 400
