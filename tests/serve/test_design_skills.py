from pathlib import Path

from fastapi.testclient import TestClient

from aurora_core.model.registry import ModelRegistry
from aurora_serve.chat.schema import ChatMessage, ChatRequest
from aurora_serve.chat.service import ChatService
from aurora_serve.design_skills.service import DesignSkillService
from aurora_serve.server import create_app


def _write_skill(root: Path, slug: str, frontmatter: str, body: str = "Use crisp layout.") -> Path:
    skill_dir = root / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return skill_dir


def test_design_skill_service_parses_open_design_frontmatter_and_files(tmp_path):
    root = tmp_path / "builtin"
    skill_dir = _write_skill(
        root,
        "dashboard",
        """
name: dashboard
description: Build dense operational dashboards.
triggers:
  - dashboard
  - analytics
od:
  mode: template
  surface: web
  scenario: dashboard
  preview:
    type: html
  design_system:
    requires:
      - charts
  example_prompt: Create a sales dashboard
""".strip(),
        "Dashboard skill body.",
    )
    (skill_dir / "assets").mkdir()
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "notes.md").write_text("Short reference.", encoding="utf-8")
    (skill_dir / "example.html").write_text("<main>Example</main>", encoding="utf-8")

    service = DesignSkillService(builtin_root=root, user_root=tmp_path / "user", external_roots=[])

    skill = service.get_skill("dashboard")

    assert skill.id == "dashboard"
    assert skill.name == "dashboard"
    assert skill.description == "Build dense operational dashboards."
    assert skill.triggers == ["dashboard", "analytics"]
    assert skill.mode == "template"
    assert skill.surface == "web"
    assert skill.scenario == "dashboard"
    assert skill.preview_type == "html"
    assert skill.example_prompt == "Create a sales dashboard"
    assert skill.has_assets is True
    assert skill.has_references is True
    assert "Dashboard skill body." in skill.body
    assert "references/notes.md" in service.list_files("dashboard")
    assert "example.html" in service.list_files("dashboard")


def test_design_skill_service_falls_back_to_directory_name_and_user_overrides_builtin(tmp_path):
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    _write_skill(
        builtin,
        "wireframe",
        "description: Built in version",
        "builtin body",
    )
    _write_skill(
        user,
        "wireframe",
        "description: User version",
        "user body",
    )

    service = DesignSkillService(builtin_root=builtin, user_root=user, external_roots=[])
    skills = service.list_skills()

    assert [skill.id for skill in skills] == ["wireframe"]
    skill = service.get_skill("wireframe")
    assert skill.name == "wireframe"
    assert skill.description == "User version"
    assert skill.source == "user"
    assert skill.body == "user body"


def test_design_skills_api_lists_and_returns_detail(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    _write_skill(
        builtin,
        "saas-landing",
        """
name: saas-landing
description: Landing page template.
od:
  mode: template
  surface: web
  preview:
    type: html
  example_prompt: Launch page for Aurora
""".strip(),
        "Landing body.",
    )
    monkeypatch.setenv("AURORA_DESIGN_SKILLS_DIR", str(builtin))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        list_resp = client.get("/api/v1/design-skills")
        detail_resp = client.get("/api/v1/design-skills/saas-landing")

    assert list_resp.status_code == 200
    assert list_resp.json()["skills"][0]["id"] == "saas-landing"
    assert list_resp.json()["skills"][0]["body"] is None
    assert detail_resp.status_code == 200
    assert detail_resp.json()["body"] == "Landing body."
    assert detail_resp.json()["examplePrompt"] == "Launch page for Aurora"


def test_design_skill_service_rejects_path_traversal(tmp_path):
    root = tmp_path / "builtin"
    _write_skill(root, "safe", "name: safe", "body")
    service = DesignSkillService(builtin_root=root, user_root=tmp_path / "user", external_roots=[])

    assert service.get_skill("../safe") is None
    assert service.list_files("../safe") == []


def test_design_skill_service_hides_adapter_pending_skills_by_default(tmp_path):
    root = tmp_path / "builtin"
    _write_skill(root, "poster", "name: poster", "body")
    pending = _write_skill(
        root,
        "figma-generate-design",
        """
name: figma-generate-design
description: Figma bridge.
od:
  status: adapter-pending
  hidden: true
  adapter:
    kind: figma
""".strip(),
        "figma body",
    )
    (pending / ".aurora-design-skill.json").write_text(
        '{"adapterStatus":"adapter-pending","dependencyType":"external-service"}',
        encoding="utf-8",
    )
    service = DesignSkillService(builtin_root=root, user_root=tmp_path / "user", external_roots=[])

    assert [skill.id for skill in service.list_skills()] == ["poster"]
    hidden = service.list_skills(include_hidden=True)[0]
    assert hidden.id == "figma-generate-design"
    assert hidden.hidden is True
    assert hidden.status == "adapter-pending"
    assert hidden.adapter_kind == "figma"
    assert hidden.dependency_type == "external-service"


def test_design_skills_api_can_include_hidden_adapter_pending_skills(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    _write_skill(
        builtin,
        "fal-generate",
        """
name: fal-generate
od:
  hidden: true
  status: adapter-pending
""".strip(),
        "fal body",
    )
    monkeypatch.setenv("AURORA_DESIGN_SKILLS_DIR", str(builtin))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        default_resp = client.get("/api/v1/design-skills")
        hidden_resp = client.get("/api/v1/design-skills?include_hidden=true")

    assert default_resp.status_code == 200
    assert default_resp.json()["skills"] == []
    assert hidden_resp.status_code == 200
    assert hidden_resp.json()["skills"][0]["id"] == "fal-generate"
    assert hidden_resp.json()["skills"][0]["hidden"] is True
    assert hidden_resp.json()["skills"][0]["status"] == "adapter-pending"


def test_design_skills_api_summarizes_adapter_backlog(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    figma = _write_skill(
        builtin,
        "figma-use",
        "name: figma-use\nod:\n  hidden: true\n  status: adapter-pending",
        "figma body",
    )
    (figma / ".aurora-design-skill.json").write_text(
        '{"adapterKind":"figma","dependencyType":"external-service","requiredTools":["figma-mcp"]}',
        encoding="utf-8",
    )
    doc = _write_skill(
        builtin,
        "pptx-generator",
        "name: pptx-generator\nod:\n  hidden: true\n  status: adapter-pending",
        "ppt body",
    )
    (doc / ".aurora-design-skill.json").write_text(
        '{"adapterKind":"document","dependencyType":"document-toolchain","requiredTools":["pptx-runtime"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AURORA_DESIGN_SKILLS_DIR", str(builtin))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        resp = client.get("/api/v1/design-skills/adapters")

    assert resp.status_code == 200
    data = resp.json()
    assert data["totalPending"] == 2
    assert data["groups"]["figma"]["count"] == 1
    assert data["groups"]["document"]["count"] == 1
    assert data["groups"]["figma"]["items"][0]["requiredTools"] == ["figma-mcp"]
    assert data["groups"]["document"]["items"][0]["dependencyType"] == "document-toolchain"


def test_design_skills_api_updates_visibility_for_management(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    _write_skill(
        builtin,
        "poster",
        "name: poster\nod:\n  hidden: true\n  status: ready",
        "poster body",
    )
    monkeypatch.setenv("AURORA_DESIGN_SKILLS_DIR", str(builtin))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))

    with TestClient(create_app()) as client:
        before = client.get("/api/v1/design-skills")
        update = client.patch("/api/v1/design-skills/poster/management", json={"hidden": False})
        after = client.get("/api/v1/design-skills")
        detail = client.get("/api/v1/design-skills/poster")

    assert before.status_code == 200
    assert before.json()["skills"] == []
    assert update.status_code == 200
    assert update.json()["hidden"] is False
    assert after.json()["skills"][0]["id"] == "poster"
    assert detail.json()["hidden"] is False


def test_chat_service_injects_active_design_skill_system_prompt(tmp_path):
    root = tmp_path / "builtin"
    skill_dir = _write_skill(
        root,
        "dashboard",
        "name: dashboard\ndescription: Dashboard skill",
        "Follow the dashboard SKILL body.",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "short.md").write_text("Use compact charts.", encoding="utf-8")
    design_skills = DesignSkillService(builtin_root=root, user_root=tmp_path / "user", external_roots=[])
    service = ChatService(ModelRegistry(), design_skill_service=design_skills)
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="Build me a dashboard")],
        ext_info={"design_skill_id": "dashboard"},
    )

    messages = service._build_messages(req)

    assert messages[0].role == "system"
    assert "Active design skill: dashboard" in messages[0].content
    assert "Follow the dashboard SKILL body." in messages[0].content
    assert "Use compact charts." in messages[0].content
    assert messages[1].role == "user"
