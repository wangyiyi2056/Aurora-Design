from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aurora_serve.metadata import storage_dir

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


@dataclass(frozen=True)
class DesignSystem:
    id: str
    title: str
    category: str
    summary: str
    swatches: list[str]
    surface: str
    body: str
    source: str
    status: str
    is_editable: bool
    root: Path
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self, include_body: bool = False, files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "name": self.title,
            "category": self.category,
            "summary": self.summary,
            "swatches": self.swatches,
            "surface": self.surface,
            "source": self.source,
            "status": self.status,
            "isEditable": self.is_editable,
            "enabled": self.enabled,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if include_body:
            payload["body"] = self.body
        if files is not None:
            payload["files"] = files
        return payload


class DesignSystemService:
    def __init__(self, builtin_root: Path | str | None = None, user_root: Path | str | None = None) -> None:
        self.builtin_root = Path(builtin_root) if builtin_root is not None else self._default_builtin_root()
        self.user_root = Path(user_root) if user_root is not None else storage_dir() / "design-systems"

    def list_systems(self) -> list[DesignSystem]:
        overrides = self._read_overrides()
        indexed: dict[str, DesignSystem] = {}
        for root, source, editable in [(self.user_root, "user", True), (self.builtin_root, "built-in", False)]:
            if not root.exists():
                continue
            for design_md in sorted(root.glob("*/DESIGN.md")):
                system = self._load_system(design_md.parent, source, editable)
                if system and system.id not in indexed:
                    if system.id in overrides:
                        system = DesignSystem(**{**{f.name: getattr(system, f.name) for f in system.__dataclass_fields__.values()}, "enabled": overrides[system.id]})
                    indexed[system.id] = system
        return sorted(indexed.values(), key=lambda item: item.title.lower())

    def get_system(self, system_id: str) -> DesignSystem | None:
        if not self._is_safe_id(system_id):
            return None
        return next((system for system in self.list_systems() if system.id == system_id), None)

    def toggle_system(self, system_id: str) -> DesignSystem | None:
        system = self.get_system(system_id)
        if system is None:
            return None
        new_enabled = not system.enabled
        overrides = self._read_overrides()
        overrides[system_id] = new_enabled
        self._write_overrides(overrides)
        return DesignSystem(**{**{f.name: getattr(system, f.name) for f in system.__dataclass_fields__.values()}, "enabled": new_enabled})

    def create_system(self, data: dict[str, Any]) -> DesignSystem:
        system_id = self._slug(str(data.get("id") or data.get("title") or data.get("name") or "design-system"))
        if not self._is_safe_id(system_id):
            raise ValueError("Invalid design system id")
        target = self.user_root / system_id
        if target.exists():
            raise ValueError("Design system already exists")
        target.mkdir(parents=True, exist_ok=False)
        now = self._now()
        title = str(data.get("title") or data.get("name") or system_id)
        category = str(data.get("category") or "Uncategorized")
        summary = str(data.get("summary") or "")
        body = str(data.get("body") or self._default_body(title, category, summary))
        (target / "DESIGN.md").write_text(body, encoding="utf-8")
        self._write_metadata(
            target,
            {
                "title": title,
                "category": category,
                "surface": str(data.get("surface") or "web"),
                "status": str(data.get("status") or "draft"),
                "createdAt": now,
                "updatedAt": now,
            },
        )
        system = self.get_system(system_id)
        if system is None:
            raise ValueError("Design system could not be created")
        return system

    def update_system(self, system_id: str, data: dict[str, Any]) -> DesignSystem | None:
        system = self.get_system(system_id)
        if system is None:
            return None
        if not system.is_editable:
            raise PermissionError("Built-in design systems are read-only")
        metadata = self._read_metadata(system.root)
        for key, source_key in [("title", "title"), ("category", "category"), ("surface", "surface"), ("status", "status")]:
            if source_key in data and data[source_key] is not None:
                metadata[key] = str(data[source_key])
        metadata["updatedAt"] = self._now()
        if isinstance(data.get("body"), str):
            (system.root / "DESIGN.md").write_text(data["body"], encoding="utf-8")
        self._write_metadata(system.root, metadata)
        return self.get_system(system_id)

    def delete_system(self, system_id: str) -> bool:
        system = self.get_system(system_id)
        if system is None:
            return False
        if not system.is_editable:
            raise PermissionError("Built-in design systems are read-only")
        for path in sorted(system.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        system.root.rmdir()
        return True

    def list_files(self, system_id: str) -> list[dict[str, Any]]:
        system = self.get_system(system_id)
        if system is None:
            return []
        root = system.root.resolve()
        files: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
            stat = path.stat()
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "name": path.name,
                    "kind": self._file_kind(path),
                    "size": stat.st_size,
                    "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                }
            )
        return files

    def read_file(self, system_id: str, relative_path: str) -> dict[str, Any] | None:
        system = self.get_system(system_id)
        clean = self._safe_relative_path(relative_path)
        if system is None or clean is None:
            return None
        root = system.root.resolve()
        path = (system.root / clean).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if not path.is_file():
            return None
        return {
            "path": clean,
            "name": path.name,
            "kind": self._file_kind(path),
            "size": path.stat().st_size,
            "content": path.read_text(encoding="utf-8", errors="replace"),
        }

    def create_revision(self, system_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        system = self.get_system(system_id)
        if system is None or not system.is_editable:
            return None
        revision = {
            "id": uuid.uuid4().hex,
            "designSystemId": system_id,
            "status": "pending",
            "feedback": str(data.get("feedback") or ""),
            "baseBody": str(data.get("baseBody") or ""),
            "proposedBody": str(data.get("proposedBody") or ""),
            "sectionTitle": data.get("sectionTitle"),
            "createdAt": self._now(),
            "updatedAt": self._now(),
        }
        revisions = self.list_revisions(system_id) or []
        revisions.append(revision)
        self._write_revisions(system.root, revisions)
        return revision

    def list_revisions(self, system_id: str) -> list[dict[str, Any]] | None:
        system = self.get_system(system_id)
        if system is None or not system.is_editable:
            return None
        path = system.root / ".aurora-revisions.json"
        if not path.exists():
            return []
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def update_revision_status(self, system_id: str, revision_id: str, status: str) -> dict[str, Any] | None:
        system = self.get_system(system_id)
        revisions = self.list_revisions(system_id)
        if system is None or revisions is None:
            return None
        for revision in revisions:
            if revision.get("id") == revision_id:
                revision["status"] = status
                revision["updatedAt"] = self._now()
                self._write_revisions(system.root, revisions)
                return revision
        return None

    def active_prompt(self, system_id: str) -> str | None:
        system = self.get_system(system_id)
        if system is None:
            return None
        parts = [
            f"## Active design system: {system.id}",
            f"Title: {system.title}",
            f"Category: {system.category}",
            f"Summary: {system.summary}" if system.summary else "",
        ]
        for name, label in [("USAGE.md", "Usage"), ("tokens.css", "Tokens CSS"), ("components.html", "Components Fixture")]:
            file = self.read_file(system.id, name)
            if file and file["content"].strip():
                parts.extend(["", f"## {label}", file["content"][:6000]])
        parts.extend(["", "## DESIGN.md", system.body])
        return "\n".join(part for part in parts if part is not None and part != "").strip()

    def _load_system(self, root: Path, source: str, editable: bool) -> DesignSystem | None:
        design_md = root / "DESIGN.md"
        if not design_md.exists():
            return None
        raw = design_md.read_text(encoding="utf-8", errors="replace")
        metadata = self._read_metadata(root)
        system_id = root.name
        title = str(metadata.get("title") or self._extract_title(raw) or system_id)
        category = str(metadata.get("category") or self._extract_category(raw) or "Uncategorized")
        summary = str(metadata.get("summary") or self._extract_summary(raw) or "")
        surface = str(metadata.get("surface") or self._extract_surface(raw) or "web")
        status = str(metadata.get("status") or ("draft" if editable else "published"))
        return DesignSystem(
            id=system_id,
            title=title,
            category=category,
            summary=summary,
            swatches=self._extract_swatches(raw),
            surface=surface,
            body=raw,
            source=source,
            status=status,
            is_editable=editable,
            root=root,
            created_at=metadata.get("createdAt") if isinstance(metadata.get("createdAt"), str) else None,
            updated_at=metadata.get("updatedAt") if isinstance(metadata.get("updatedAt"), str) else None,
        )

    def _default_builtin_root(self) -> Path:
        env_root = os.getenv("AURORA_DESIGN_SYSTEMS_DIR")
        if env_root:
            return Path(env_root)
        return Path.cwd() / "design-systems"

    def _read_metadata(self, root: Path) -> dict[str, Any]:
        path = root / ".aurora-design-system.json"
        if not path.exists():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _write_metadata(self, root: Path, metadata: dict[str, Any]) -> None:
        (root / ".aurora-design-system.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    def _write_revisions(self, root: Path, revisions: list[dict[str, Any]]) -> None:
        (root / ".aurora-revisions.json").write_text(json.dumps(revisions, indent=2) + "\n", encoding="utf-8")

    def _overrides_path(self) -> Path:
        return self.user_root / ".aurora-enabled-overrides.json"

    def _read_overrides(self) -> dict[str, bool]:
        path = self._overrides_path()
        if not path.exists():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _write_overrides(self, overrides: dict[str, bool]) -> None:
        self.user_root.mkdir(parents=True, exist_ok=True)
        self._overrides_path().write_text(json.dumps(overrides, indent=2) + "\n", encoding="utf-8")

    def _extract_title(self, raw: str) -> str:
        match = re.search(r"^#\s+(.+?)\s*$", raw, re.MULTILINE)
        if not match:
            return ""
        return re.sub(r"^Design System Inspired by\s+", "", match.group(1).strip(), flags=re.I)

    def _extract_category(self, raw: str) -> str:
        match = re.search(r"^>\s*Category:\s*(.+?)\s*$", raw, re.MULTILINE | re.I)
        return match.group(1).strip() if match else ""

    def _extract_summary(self, raw: str) -> str:
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith(">") and not re.match(r"^>\s*Category:", stripped, re.I):
                return stripped.lstrip(">").strip()
        return ""

    def _extract_surface(self, raw: str) -> str:
        match = re.search(r"^>\s*Surface:\s*(web|image|video|audio)\s*$", raw, re.MULTILINE | re.I)
        return match.group(1).lower() if match else ""

    def _extract_swatches(self, raw: str) -> list[str]:
        seen: set[str] = set()
        swatches: list[str] = []
        for match in HEX_RE.finditer(raw):
            color = match.group(0)
            key = color.lower()
            if key in seen:
                continue
            seen.add(key)
            swatches.append(color)
            if len(swatches) >= 12:
                break
        return swatches

    def _file_kind(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".html":
            return "page"
        if suffix == ".css":
            return "stylesheet"
        if suffix in {".md", ".txt"}:
            return "document"
        if suffix in {".json", ".jsonl"}:
            return "data"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            return "image"
        return "asset"

    def _safe_relative_path(self, value: str) -> str | None:
        if not value or "\\" in value:
            return None
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            return None
        return path.as_posix()

    def _is_safe_id(self, system_id: str) -> bool:
        return bool(system_id) and "/" not in system_id and "\\" not in system_id and ".." not in system_id

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
        return slug or "design-system"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _default_body(self, title: str, category: str, summary: str) -> str:
        return f"# {title}\n\n> Category: {category}\n> {summary}\n"
