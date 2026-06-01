from pathlib import Path

from fastapi.testclient import TestClient

from aurora_core.model.registry import ModelRegistry
from aurora_serve.chat.schema import ChatMessage, ChatRequest
from aurora_serve.chat.service import ChatService
from aurora_serve.design_systems.service import DesignSystemService
from aurora_serve.server import create_app


def _write_system(root: Path, slug: str, body: str, extra: dict[str, str] | None = None) -> Path:
    system_dir = root / slug
    system_dir.mkdir(parents=True)
    (system_dir / "DESIGN.md").write_text(body, encoding="utf-8")
    for name, content in (extra or {}).items():
        path = system_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return system_dir


SYSTEM_BODY = """# Design System Inspired by Vercel

> Category: Developer Tools
> Frontend deployment. Black and white precision.

## 1. Visual Theme & Atmosphere

Sharp monochrome UI with #ffffff canvas, #171717 text, and #0070f3 links.

## 2. Color

- Black: #171717
- White: #ffffff
- Blue: #0070f3

## 3. Typography

Use geometric sans text.
"""


def test_design_system_service_parses_design_md_and_package_files(tmp_path):
    root = tmp_path / "builtin"
    _write_system(
        root,
        "vercel",
        SYSTEM_BODY,
        {
            "open-design.json": '{"title":"Vercel"}',
            "USAGE.md": "Read DESIGN.md first.",
            "tokens.css": ":root { --bg: #ffffff; }",
            "preview/app.html": "<main>Preview</main>",
        },
    )
    service = DesignSystemService(builtin_root=root, user_root=tmp_path / "user")

    system = service.get_system("vercel")

    assert system is not None
    assert system.id == "vercel"
    assert system.title == "Vercel"
    assert system.category == "Developer Tools"
    assert system.summary == "Frontend deployment. Black and white precision."
    assert system.swatches[:3] == ["#ffffff", "#171717", "#0070f3"]
    assert system.source == "built-in"
    assert system.status == "published"
    assert system.is_editable is False
    assert "preview/app.html" in [item["path"] for item in service.list_files("vercel")]
    assert service.read_file("vercel", "USAGE.md") is not None


def test_design_system_service_exposes_default_config_and_usage_fallback(tmp_path):
    root = tmp_path / "builtin"
    _write_system(root, "default", SYSTEM_BODY)
    service = DesignSystemService(
        builtin_root=root,
        user_root=tmp_path / "user",
        default_system_id="default",
        token_channel_enabled=True,
    )

    prompt = service.active_prompt("default")

    assert service.default_system_id == "default"
    assert service.token_channel_enabled is True
    assert prompt is not None
    assert "## How to use this design system" in prompt
    assert "Read DESIGN.md for visual principles" in prompt
    assert "## Active design system: default" in prompt


def test_design_system_service_user_overrides_builtin(tmp_path):
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    _write_system(builtin, "brand", "# Builtin\n\n> Category: Modern & Minimal\n> Builtin summary.")
    _write_system(user, "brand", "# User Brand\n\n> Category: Productivity & SaaS\n> User summary.")

    service = DesignSystemService(builtin_root=builtin, user_root=user)
    systems = service.list_systems()

    assert [system.id for system in systems] == ["brand"]
    assert systems[0].title == "User Brand"
    assert systems[0].source == "user"
    assert systems[0].is_editable is True


def test_design_system_service_rejects_path_traversal(tmp_path):
    root = tmp_path / "builtin"
    _write_system(root, "safe", SYSTEM_BODY)
    service = DesignSystemService(builtin_root=root, user_root=tmp_path / "user")

    assert service.get_system("../safe") is None
    assert service.read_file("safe", "../DESIGN.md") is None
    assert service.list_files("../safe") == []


def test_design_systems_api_lists_detail_preview_and_user_crud(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    _write_system(builtin, "vercel", SYSTEM_BODY)
    monkeypatch.setenv("AURORA_DESIGN_SYSTEMS_DIR", str(builtin))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        list_resp = client.get("/api/v1/design-systems")
        detail_resp = client.get("/api/v1/design-systems/vercel")
        preview_resp = client.get("/api/v1/design-systems/vercel/preview")
        missing_preview = client.get("/api/v1/design-systems/missing/preview")
        builtin_patch = client.patch("/api/v1/design-systems/vercel", json={"title": "Changed"})
        created = client.post(
            "/api/v1/design-systems",
            json={
                "id": "aurora",
                "title": "Aurora",
                "summary": "Dark analytical interface.",
                "category": "Developer Tools",
                "body": "# Aurora\n\n> Category: Developer Tools\n> Dark analytical interface.",
            },
        )
        updated = client.patch("/api/v1/design-systems/aurora", json={"status": "published"})
        files = client.get("/api/v1/design-systems/aurora/files")
        deleted = client.delete("/api/v1/design-systems/aurora")

    assert list_resp.status_code == 200
    assert list_resp.json()["designSystems"][0]["id"] == "vercel"
    assert "body" not in list_resp.json()["designSystems"][0]
    assert detail_resp.status_code == 200
    assert "Sharp monochrome UI" in detail_resp.json()["body"]
    assert preview_resp.status_code == 200
    assert "text/html" in preview_resp.headers["content-type"]
    assert "Design system preview" in preview_resp.text
    assert missing_preview.status_code == 404
    assert builtin_patch.status_code == 403
    assert created.status_code == 201
    assert created.json()["id"] == "aurora"
    assert created.json()["isEditable"] is True
    assert updated.status_code == 200
    assert updated.json()["status"] == "published"
    assert files.status_code == 200
    assert "DESIGN.md" in [item["path"] for item in files.json()["files"]]
    assert deleted.status_code == 204


def test_design_system_revisions_api(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_DESIGN_SYSTEMS_DIR", str(tmp_path / "builtin"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        client.post(
            "/api/v1/design-systems",
            json={"id": "draft", "title": "Draft", "body": "# Draft\n\n> Category: Developer Tools\n> Summary."},
        )
        created = client.post(
            "/api/v1/design-systems/draft/revisions",
            json={"feedback": "Make it sharper.", "baseBody": "old", "proposedBody": "new"},
        )
        listed = client.get("/api/v1/design-systems/draft/revisions")
        patched = client.patch(
            f"/api/v1/design-systems/draft/revisions/{created.json()['revision']['id']}",
            json={"status": "accepted"},
        )

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()["revisions"][0]["feedback"] == "Make it sharper."
    assert patched.status_code == 200
    assert patched.json()["revision"]["status"] == "accepted"


def test_chat_service_injects_active_design_system_after_design_skill(tmp_path):
    systems_root = tmp_path / "systems"
    _write_system(systems_root, "vercel", SYSTEM_BODY, {"USAGE.md": "Use the Vercel package."})
    systems = DesignSystemService(builtin_root=systems_root, user_root=tmp_path / "user-systems")

    class SkillService:
        def active_prompt(self, skill_id: str) -> str:
            return f"## Active design skill: {skill_id}\nFollow skill."

    service = ChatService(
        ModelRegistry(),
        design_skill_service=SkillService(),
        design_system_service=systems,
    )
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="Build a page")],
        ext_info={"design_skill_id": "dashboard", "design_system_id": "vercel"},
    )

    messages = service._build_messages(req)

    assert messages[0].role == "system"
    assert "Active design skill: dashboard" in messages[0].content
    assert "Active design system: vercel" in messages[1].content
    assert messages[1].content.index("Use the Vercel package.") < messages[1].content.index("Sharp monochrome UI")
    assert messages[2].role == "user"
