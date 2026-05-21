from __future__ import annotations

import base64
import io
import mimetypes
import os
from pathlib import Path
from typing import Literal
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, UploadFile

from aurora_serve.metadata import storage_dir

WorkspaceFileKind = Literal[
    "html",
    "image",
    "video",
    "audio",
    "sketch",
    "text",
    "code",
    "markdown",
    "json",
    "pdf",
    "document",
    "presentation",
    "spreadsheet",
    "binary",
]


class WorkspaceFileService:
    """Filesystem-backed, workspace-scoped file operations."""

    def __init__(self, root: Path | None = None):
        self.root = root or storage_dir() / "workspaces"
        self.root.mkdir(parents=True, exist_ok=True)

    def workspace_root(self, workspace_id: str) -> Path:
        safe_id = self._validate_workspace_id(workspace_id)
        root = (self.root / safe_id).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def resolve_path(self, workspace_id: str, raw_path: str) -> Path:
        rel = self._validate_relative_path(raw_path)
        root = self.workspace_root(workspace_id)
        candidate = (root / rel).resolve(strict=False)
        try:
            os.path.commonpath([str(root), str(candidate)])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Unsafe workspace path") from exc
        if os.path.commonpath([str(root), str(candidate)]) != str(root):
            raise HTTPException(status_code=400, detail="Unsafe workspace path")
        return candidate

    def list_files(self, workspace_id: str) -> list[dict]:
        root = self.workspace_root(workspace_id)
        files: list[dict] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            files.append(self.file_meta(workspace_id, rel))
        return sorted(files, key=lambda item: item["name"])

    def file_meta(self, workspace_id: str, raw_path: str) -> dict:
        path = self.resolve_path(workspace_id, raw_path)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        stat = path.stat()
        rel = path.relative_to(self.workspace_root(workspace_id)).as_posix()
        mime = infer_mime(rel)
        return {
            "name": rel,
            "path": rel,
            "type": "file",
            "size": stat.st_size,
            "mtime": stat.st_mtime * 1000,
            "kind": infer_kind(rel, mime),
            "mime": mime,
        }

    def write_file(
        self,
        workspace_id: str,
        name: str,
        content: str,
        encoding: str = "utf8",
        overwrite: bool = True,
    ) -> dict:
        path = self.resolve_path(workspace_id, name)
        if path.exists() and not overwrite:
            raise HTTPException(status_code=409, detail="File already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        if encoding == "base64":
            body = base64.b64decode(content)
        elif encoding in {"utf8", "utf-8"}:
            body = content.encode("utf-8")
        else:
            raise HTTPException(status_code=400, detail="Unsupported encoding")
        path.write_bytes(body)
        return self.file_meta(workspace_id, name)

    async def upload_files(
        self,
        workspace_id: str,
        files: list[UploadFile],
        base_dir: str = "",
    ) -> list[dict]:
        uploaded: list[dict] = []
        prefix = self._validate_optional_dir(base_dir)
        for file in files:
            filename = Path(file.filename or "upload.bin").name
            if not filename:
                filename = "upload.bin"
            rel = f"{prefix}/{filename}" if prefix else filename
            path = self.resolve_path(workspace_id, rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(await file.read())
            meta = self.file_meta(workspace_id, rel)
            meta["originalName"] = file.filename or filename
            uploaded.append(meta)
        return uploaded

    def rename_file(self, workspace_id: str, old_name: str, new_name: str) -> dict:
        old_path = self.resolve_path(workspace_id, old_name)
        new_path = self.resolve_path(workspace_id, new_name)
        if not old_path.exists() or not old_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        if new_path.exists():
            raise HTTPException(status_code=409, detail="File already exists")
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        return {
            "oldName": self._validate_relative_path(old_name),
            "newName": self._validate_relative_path(new_name),
            "file": self.file_meta(workspace_id, new_name),
        }

    def delete_file(self, workspace_id: str, name: str) -> None:
        path = self.resolve_path(workspace_id, name)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        path.unlink()

    def build_archive(self, workspace_id: str, root_dir: str = "") -> tuple[bytes, str]:
        root = self.workspace_root(workspace_id)
        archive_root = root if not root_dir else self.resolve_path(workspace_id, root_dir)
        if not archive_root.exists() or not archive_root.is_dir():
            raise HTTPException(status_code=404, detail="Archive root not found")

        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for path in archive_root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                archive.write(path, rel)
        filename = f"{Path(root_dir).name if root_dir else workspace_id}.zip"
        return buffer.getvalue(), filename

    @staticmethod
    def _validate_workspace_id(workspace_id: str) -> str:
        safe = workspace_id.strip()
        if not safe or "/" in safe or "\\" in safe or safe in {".", ".."}:
            raise HTTPException(status_code=400, detail="Unsafe workspace id")
        return safe

    @staticmethod
    def _validate_relative_path(raw_path: str) -> str:
        decoded = unquote(str(raw_path or "")).replace("\\", "/")
        path = Path(decoded)
        parts = [part for part in decoded.split("/") if part]
        if (
            not decoded
            or path.is_absolute()
            or any(part in {".", ".."} for part in parts)
        ):
            raise HTTPException(status_code=400, detail="Unsafe workspace path")
        return "/".join(parts)

    def _validate_optional_dir(self, raw_dir: str) -> str:
        if not raw_dir:
            return ""
        return self._validate_relative_path(raw_dir)


def infer_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    if mime:
        return mime
    suffix = Path(name).suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".py", ".sql", ".css"}:
        return "text/plain"
    return "application/octet-stream"


def infer_kind(name: str, mime: str) -> WorkspaceFileKind:
    suffix = Path(name).suffix.lower()
    if mime == "text/html" or suffix in {".html", ".htm"}:
        return "html"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if suffix in {".sketch"}:
        return "sketch"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if mime == "application/json" or suffix == ".json":
        return "json"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".py", ".sql", ".css", ".scss", ".vue"}:
        return "code"
    if mime == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if suffix in {".doc", ".docx"}:
        return "document"
    if suffix in {".ppt", ".pptx"}:
        return "presentation"
    if suffix in {".xls", ".xlsx", ".csv"}:
        return "spreadsheet"
    if mime.startswith("text/"):
        return "text"
    return "binary"
