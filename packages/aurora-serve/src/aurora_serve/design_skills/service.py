from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal installs.
    yaml = None

from aurora_serve.metadata import storage_dir


@dataclass(frozen=True)
class DesignSkill:
    id: str
    name: str
    description: str
    source: str
    mode: str
    surface: str
    scenario: str
    preview_type: str
    example_prompt: str
    has_assets: bool
    has_references: bool
    triggers: list[str]
    body: str | None
    root: Path
    hidden: bool = False
    status: str = "ready"
    adapter_kind: str = ""
    dependency_type: str = ""
    required_tools: list[str] | None = None

    def to_dict(self, include_body: bool = False, files: list[str] | None = None) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "mode": self.mode,
            "surface": self.surface,
            "scenario": self.scenario,
            "previewType": self.preview_type,
            "examplePrompt": self.example_prompt,
            "hasAssets": self.has_assets,
            "hasReferences": self.has_references,
            "triggers": self.triggers,
            "body": self.body if include_body else None,
            "hidden": self.hidden,
            "status": self.status,
            "adapterKind": self.adapter_kind,
            "dependencyType": self.dependency_type,
            "requiredTools": self.required_tools or [],
        }
        if files is not None:
            payload["files"] = files
        return payload


class DesignSkillService:
    """Scans Claude/Open Design style SKILL.md directories."""

    def __init__(
        self,
        builtin_root: Path | str | None = None,
        user_root: Path | str | None = None,
        external_roots: list[Path | str] | None = None,
    ) -> None:
        self.user_root = Path(user_root) if user_root is not None else storage_dir() / "design-skills"
        self.builtin_root = Path(builtin_root) if builtin_root is not None else self._default_builtin_root()
        self.external_roots = [Path(root) for root in (external_roots if external_roots is not None else self._env_external_roots())]

    def list_skills(self, include_hidden: bool = False) -> list[DesignSkill]:
        indexed: dict[str, DesignSkill] = {}
        for root, source in self._roots():
            if not root.exists():
                continue
            for skill_md in sorted(root.glob("*/SKILL.md")):
                skill = self._load_skill(skill_md.parent, source)
                if skill and skill.hidden and not include_hidden:
                    continue
                if skill and skill.id not in indexed:
                    indexed[skill.id] = skill
        return sorted(indexed.values(), key=lambda item: item.name.lower())

    def get_skill(self, skill_id: str, include_hidden: bool = True) -> DesignSkill | None:
        if not self._is_safe_id(skill_id):
            return None
        for skill in self.list_skills(include_hidden=include_hidden):
            if skill.id == skill_id:
                return skill
        return None

    def list_files(self, skill_id: str) -> list[str]:
        skill = self.get_skill(skill_id)
        if skill is None:
            return []
        root = skill.root.resolve()
        files: list[str] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
                resolved.relative_to(root)
            except ValueError:
                continue
            files.append(path.relative_to(root).as_posix())
        return files

    def update_management(
        self,
        skill_id: str,
        *,
        hidden: bool | None = None,
        status: str | None = None,
    ) -> DesignSkill | None:
        skill = self.get_skill(skill_id, include_hidden=True)
        if skill is None:
            return None
        sidecar_path = skill.root / ".aurora-design-skill.json"
        sidecar = self._load_sidecar(skill.root)
        if hidden is not None:
            sidecar["hidden"] = hidden
        if status is not None:
            sidecar["status"] = status
        sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
        return self.get_skill(skill_id, include_hidden=True)

    def active_prompt(self, skill_id: str) -> str | None:
        skill = self.get_skill(skill_id)
        if skill is None or not skill.body:
            return None
        parts = [
            f"## Active design skill: {skill.id}",
            f"Name: {skill.name}",
            f"Description: {skill.description}" if skill.description else "",
            "",
            skill.body,
        ]
        references = self.short_reference_context(skill)
        if references:
            parts.extend(["", "## Skill references", references])
        return "\n".join(part for part in parts if part is not None).strip()

    def adapter_backlog(self) -> dict[str, Any]:
        groups: dict[str, dict[str, Any]] = {}
        pending = [
            skill
            for skill in self.list_skills(include_hidden=True)
            if skill.status == "adapter-pending"
        ]
        for skill in pending:
            key = skill.adapter_kind or "unknown"
            group = groups.setdefault(key, {"count": 0, "items": []})
            group["count"] += 1
            group["items"].append(
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "source": skill.source,
                    "status": skill.status,
                    "dependencyType": skill.dependency_type,
                    "requiredTools": skill.required_tools or [],
                }
            )
        return {"totalPending": len(pending), "groups": groups}

    def short_reference_context(self, skill: DesignSkill, max_chars: int = 8000) -> str:
        references_dir = skill.root / "references"
        if not references_dir.exists() or not references_dir.is_dir():
            return ""
        remaining = max_chars
        chunks: list[str] = []
        for path in sorted(references_dir.rglob("*")):
            if remaining <= 0 or not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                continue
            relative = path.relative_to(skill.root).as_posix()
            snippet = text[: min(len(text), 4000, remaining)]
            chunks.append(f"### {relative}\n{snippet}")
            remaining -= len(snippet)
        return "\n\n".join(chunks)

    def _roots(self) -> list[tuple[Path, str]]:
        return [(self.user_root, "user"), *[(root, "external") for root in self.external_roots], (self.builtin_root, "builtin")]

    def _default_builtin_root(self) -> Path:
        env_root = os.getenv("AURORA_DESIGN_SKILLS_DIR")
        if env_root:
            return Path(env_root)
        return Path.cwd() / "design-skills"

    def _env_external_roots(self) -> list[Path]:
        raw = os.getenv("AURORA_DESIGN_SKILL_ROOTS", "")
        return [Path(item) for item in raw.split(os.pathsep) if item.strip()]

    def _load_skill(self, root: Path, source: str) -> DesignSkill | None:
        skill_md = root / "SKILL.md"
        if not skill_md.exists():
            return None
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        metadata, body = self._parse_skill_md(text)
        od = metadata.get("od") if isinstance(metadata.get("od"), dict) else {}
        sidecar = self._load_sidecar(root)
        preview = od.get("preview") if isinstance(od.get("preview"), dict) else {}
        adapter = od.get("adapter") if isinstance(od.get("adapter"), dict) else {}
        design_system = od.get("design_system") if isinstance(od.get("design_system"), dict) else {}
        triggers = metadata.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [triggers]
        elif not isinstance(triggers, list):
            triggers = []

        skill_id = str(metadata.get("name") or root.name).strip() or root.name
        if not self._is_safe_id(skill_id):
            skill_id = root.name
        hidden = bool(sidecar.get("hidden", od.get("hidden", False)))
        status = str(sidecar.get("status") or sidecar.get("adapterStatus") or od.get("status") or ("adapter-pending" if hidden else "ready"))

        return DesignSkill(
            id=skill_id,
            name=str(metadata.get("name") or root.name),
            description=str(metadata.get("description") or ""),
            source=source,
            mode=str(od.get("mode") or "prompt"),
            surface=str(od.get("surface") or od.get("platform") or ""),
            scenario=str(od.get("scenario") or ""),
            preview_type=str(preview.get("type") or ""),
            example_prompt=str(od.get("example_prompt") or metadata.get("example_prompt") or ""),
            has_assets=(root / "assets").is_dir(),
            has_references=(root / "references").is_dir(),
            triggers=[str(item) for item in triggers],
            body=body.strip(),
            root=root,
            hidden=hidden,
            status=status,
            adapter_kind=str(sidecar.get("adapterKind") or adapter.get("kind") or ""),
            dependency_type=str(sidecar.get("dependencyType") or od.get("dependency_type") or ""),
            required_tools=[
                str(item)
                for item in sidecar.get("requiredTools", [])
                if item
            ]
            if isinstance(sidecar.get("requiredTools"), list)
            else [],
        )

    def _load_sidecar(self, root: Path) -> dict[str, Any]:
        sidecar = root / ".aurora-design-skill.json"
        if not sidecar.exists():
            return {}
        try:
            parsed = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_skill_md(self, text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        metadata = self._parse_frontmatter(parts[1])
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata, parts[2].lstrip()

    def _parse_frontmatter(self, frontmatter: str) -> dict[str, Any]:
        if yaml is not None:
            return yaml.safe_load(frontmatter) or {}
        result: dict[str, Any] = {}
        stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]
        current_list_key: str | None = None
        current_list_parent: dict[str, Any] | None = None
        current_list_indent = -1
        for raw_line in frontmatter.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            line = raw_line.strip()
            if line.startswith("- ") and current_list_key:
                if current_list_parent is None:
                    continue
                if not isinstance(current_list_parent.get(current_list_key), list):
                    current_list_parent[current_list_key] = []
                    while len(stack) > 1 and stack[-1][0] > current_list_indent:
                        stack.pop()
                current_list_parent[current_list_key].append(self._parse_scalar(line[2:].strip()))
                continue
            if indent <= current_list_indent:
                current_list_key = None
                current_list_parent = None
                current_list_indent = -1
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if value == "":
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
                current_list_key = key
                current_list_parent = parent
                current_list_indent = indent
                continue
            if value == "[]":
                parent[key] = []
            elif value.startswith("[") and value.endswith("]"):
                parent[key] = [
                    self._parse_scalar(item.strip())
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
            else:
                parent[key] = self._parse_scalar(value)
            current_list_key = key
            current_list_parent = parent
            current_list_indent = indent
        return result

    def _parse_scalar(self, value: str) -> Any:
        unquoted = value.strip().strip('"').strip("'")
        if unquoted.lower() == "true":
            return True
        if unquoted.lower() == "false":
            return False
        return unquoted

    def _is_safe_id(self, skill_id: str) -> bool:
        return bool(skill_id) and "/" not in skill_id and "\\" not in skill_id and ".." not in skill_id
