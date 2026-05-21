# Fileworkspace Feature Specification

> Version: 1.0.0 | Last Updated: 2026-05-20 | Status: In Progress | Reference: `/Users/wyl/Desktop/github/open-design`

## 1. Goal

Add a project-scoped file workspace to Aurora for previewing, organizing, editing, and exporting generated or uploaded artifacts such as HTML, images, Markdown, JSON, text, audio, video, PDFs, and office documents. The feature should preserve 80-100% of the useful behavior from open-design's file workspace while fitting Aurora's FastAPI backend, React frontend, Electron desktop shell, and existing chat/session architecture.

The first implementation target is an 85% core migration: project files, tabbed browsing, robust previews, upload/delete/rename/write APIs, and chat artifact integration. Advanced open-design features such as live artifacts, preview comments, inspect/manual-edit bridges, and deploy flows are explicitly staged for later phases.

Current v1 implementation status:

- Implemented: workspace file API, safe path resolution, list/raw/write/upload/rename/delete/archive, frontend services, persisted tabs, file browser, upload button, drag/drop upload, new-file flow, rename/delete, HTML/image/SVG/Markdown/text/code/JSON/audio/video/PDF/document/presentation/spreadsheet/binary/sketch preview, chat-page workspace panel using session id as workspace id, generated stream artifact persistence, generated HTML auto-open, and HTML export actions for PDF/PNG/HTML/Markdown/ZIP.
- Remaining for full open-design parity: tab reorder, paste-as-file UI, multi-select batch actions, richer Office document extraction previews, deploy/share provider flows, React component execution preview, Playwright visual coverage, and i18n extraction.

## 2. Current Project Fit

Aurora already has the pieces needed for a clean implementation:

- Backend: FastAPI routers under `packages/aurora-serve/src/aurora_serve`, SQLite metadata in `metadata.py`, and a simple `FileService`.
- Frontend: React 18 + TypeScript + Vite, feature-based modules under `frontend/src/features`, Zustand stores, and existing HTML preview components.
- Desktop: Electron starts the Python backend and exposes the backend URL through `window.electronAPI.getBackendUrl()`.
- Chat: `ChatService` streams typed events and persists sessions; React agent output already derives HTML artifacts in memory.

The current specs in `specs/aurora-platform-documentation` describe the implemented platform, but they do not define a fileworkspace. This spec is therefore additive and should be treated as the source of truth for the new feature.

## 3. Reference Scope From open-design

Reference files:

- `/Users/wyl/Desktop/github/open-design/apps/web/src/components/FileWorkspace.tsx`
- `/Users/wyl/Desktop/github/open-design/apps/web/src/components/DesignFilesPanel.tsx`
- `/Users/wyl/Desktop/github/open-design/apps/web/src/components/FileViewer.tsx`
- `/Users/wyl/Desktop/github/open-design/apps/web/src/runtime/file-ops.ts`
- `/Users/wyl/Desktop/github/open-design/apps/web/src/runtime/srcdoc.ts`
- `/Users/wyl/Desktop/github/open-design/apps/web/src/runtime/exports.ts`
- `/Users/wyl/Desktop/github/open-design/packages/contracts/src/api/files.ts`
- `/Users/wyl/Desktop/github/open-design/apps/daemon/src/project-routes.ts`
- `/Users/wyl/Desktop/github/open-design/apps/daemon/src/projects.ts`

Reusable concepts:

- Project-scoped file model with `name`, `path`, `size`, `mtime`, `kind`, and `mime`.
- Raw file route for iframe/media/image access.
- Text write route and multipart upload route.
- Tabbed workspace with a sticky file browser tab.
- File browser with grouping, sorting, selection, drag/drop upload, rename, delete, and inline preview.
- Viewer dispatch by file kind.
- Sandboxed HTML preview with relative asset support.
- File operation summary derived from agent Read/Write/Edit tool events.

Not directly reusable without adaptation:

- Express daemon routes.
- `@open-design/contracts` package imports.
- open-design analytics, deployment, live artifact, design-system, and comment systems.
- Host package helpers such as `@open-design/host`.
- Large all-in-one `FileViewer.tsx`; Aurora should split viewers into smaller files.

## 4. Functional Requirements

### 4.1 Workspace Ownership

Each chat session or project-like surface must have exactly one workspace id.

Required behavior:

- New chat sessions create or lazily resolve a workspace id.
- Existing sessions can load their workspace id from persisted metadata.
- Workspace files are stored on disk under `data/workspaces/{workspace_id}/`.
- A workspace may contain nested paths such as `reports/index.html`, `assets/logo.png`, and `styles/app.css`.
- Files must never escape the workspace root, even through `../`, symlinks, URL encoding, or absolute paths.

Recommended workspace id source:

- Chat session id for normal chat.
- App id or project id for future construct/project surfaces.

### 4.2 File Operations

The backend must support:

- List workspace files.
- Read a raw file by relative path.
- Upload one or many binary files.
- Write a text/base64 file.
- Rename a file.
- Delete a file.
- Defer workspace-wide search by name/content to Phase 6 unless it is needed by chat integration.
- Produce simplified document previews for PDF, DOCX, PPTX, and XLSX when lightweight extraction is practical; otherwise return a structured unsupported preview response.

The frontend must support:

- Drag/drop upload.
- File picker upload.
- Paste text as a file.
- Create new HTML/text/Markdown files.
- Rename files.
- Delete one or many files.
- Refresh file list.
- Open a file in a tab.
- Close and reorder tabs.
- Persist tab state per workspace.

### 4.3 File Kinds

The platform must classify files into these kinds:

```ts
export type WorkspaceFileKind =
  | "html"
  | "image"
  | "video"
  | "audio"
  | "text"
  | "code"
  | "markdown"
  | "json"
  | "pdf"
  | "document"
  | "presentation"
  | "spreadsheet"
  | "binary"
```

Classification should use MIME first and extension second. Unknown files fall back to `binary`.

### 4.4 Preview Requirements

Required viewer support:

- HTML: sandboxed iframe with refresh, viewport presets, zoom, open in new tab, download.
- Image: PNG, JPEG, GIF, WebP, AVIF, BMP, SVG.
- SVG: source and preview modes if feasible.
- Markdown: rendered view and source fallback.
- JSON: formatted source without precision-destroying rewrites.
- Text/code: line-numbered, copyable source view.
- Audio/video: native controls, raw URL backed by streaming route.
- PDF/Office: simplified preview when possible, otherwise download/open fallback.
- Binary: metadata-only fallback.

HTML preview requirements:

- Full HTML documents pass through unchanged except for safe preview wrapper additions.
- HTML fragments are wrapped in a minimal document.
- Relative assets must resolve against the file's workspace directory.
- Preview iframe must be sandboxed.
- `script` support is allowed for generated prototypes, but remote network access should be limited by CSP where possible.
- Cache busting must be available after file updates.

### 4.5 Tabs

The workspace has:

- A sticky root tab named "Files".
- One tab per opened file.
- Active tab persisted per workspace.
- Reorder by drag.
- Close tab.
- Auto-open newly generated or uploaded HTML when appropriate.
- If the active file is deleted, return to the previous tab or the Files tab.
- If a file is renamed, update the matching tab id.

Initial persistence can use localStorage/Zustand. Later persistence should move into session metadata.

### 4.6 Chat and Agent Integration

Chat output should become workspace files instead of only in-memory artifacts.

Required behavior:

- When React agent output contains `output_type: "html"`, write an `.html` file into the session workspace.
- When output contains image/base64/file-like content, write the matching file.
- The workspace refreshes after a file-producing event.
- Assistant messages can show a compact "files touched/generated" summary.
- Clicking a generated file summary opens it in the workspace.
- Existing `ReactAgentWorkspace` right-side artifact tabs should be replaced or backed by `FileWorkspace`.

Tool event integration:

- Aggregate Read/Write/Edit-like events from `AgentEvent`.
- Show basename, full path tooltip, operation types, counts, and status.
- Clicking a known workspace file opens it.

### 4.7 Security

Backend path safety:

- Normalize and resolve every requested path.
- Reject absolute paths.
- Reject empty paths for file operations except list.
- Reject path traversal.
- Reject symlink escapes.
- Keep hidden internal metadata files inaccessible unless explicitly needed.

Upload safety:

- Enforce file size limit.
- Enforce batch size limit.
- Sanitize names while preserving nested paths only when the caller intentionally provides them.
- Detect filename conflicts and return a structured error unless overwrite is explicitly allowed.

Preview safety:

- HTML runs in sandboxed iframes.
- Raw file routes return correct MIME.
- Audio/video range requests do not load whole large files into memory.
- Browser-origin rules should not allow arbitrary remote origins to read local workspace files.

### 4.8 Internationalization

All visible labels must be compatible with the current i18n setup.

Minimum keys:

- Files
- Upload
- Paste
- New file
- Rename
- Delete
- Refresh
- Preview
- Source
- Download
- Open in new tab
- No files
- Unsupported preview
- Upload failed
- File exists
- Delete selected
- Sort by name/type/modified

### 4.9 Accessibility and UX

Required:

- Keyboard reachable toolbar and tabs.
- Visible focus states.
- Buttons use icons and accessible labels/tooltips.
- Destructive actions require confirmation for batch delete.
- Loading, empty, error, and unsupported states are explicit.
- Text must not overflow controls at desktop or mobile widths.
- Preview canvas must remain usable in narrow widths.

## 5. API Contract

All endpoints are under `/api/v1`.

### 5.1 List Files

`GET /workspaces/{workspace_id}/files`

Response:

```json
{
  "files": [
    {
      "name": "reports/index.html",
      "path": "reports/index.html",
      "type": "file",
      "size": 12345,
      "mtime": 1790000000000,
      "kind": "html",
      "mime": "text/html"
    }
  ]
}
```

### 5.2 Read Raw File

`GET /workspaces/{workspace_id}/raw/{path:path}`

Behavior:

- Returns the file body with its MIME.
- Supports `Range` for audio/video.
- Returns 404 for missing files.
- Returns 400 for unsafe paths.

### 5.3 Write Text or Base64 File

`POST /workspaces/{workspace_id}/files`

Request:

```json
{
  "name": "reports/index.html",
  "content": "<!doctype html><html></html>",
  "encoding": "utf8",
  "overwrite": true
}
```

Response:

```json
{
  "file": {
    "name": "reports/index.html",
    "path": "reports/index.html",
    "type": "file",
    "size": 31,
    "mtime": 1790000000000,
    "kind": "html",
    "mime": "text/html"
  }
}
```

### 5.4 Upload Files

`POST /workspaces/{workspace_id}/upload`

Multipart fields:

- `files`: one or more files.
- Optional `base_dir`: workspace-relative directory.

Response:

```json
{
  "files": [
    {
      "name": "assets/logo.png",
      "path": "assets/logo.png",
      "size": 5120,
      "originalName": "logo.png",
      "kind": "image",
      "mime": "image/png"
    }
  ],
  "failed": []
}
```

### 5.5 Rename File

`POST /workspaces/{workspace_id}/files/rename`

Request:

```json
{
  "from": "old.html",
  "to": "new.html"
}
```

Response:

```json
{
  "oldName": "old.html",
  "newName": "new.html",
  "file": {
    "name": "new.html",
    "path": "new.html",
    "type": "file",
    "size": 100,
    "mtime": 1790000000000,
    "kind": "html",
    "mime": "text/html"
  }
}
```

### 5.6 Delete File

`DELETE /workspaces/{workspace_id}/raw/{path:path}`

Response:

```json
{ "ok": true }
```

### 5.7 Document Preview

`GET /workspaces/{workspace_id}/files/{path:path}/preview`

Response:

```json
{
  "kind": "pdf",
  "title": "report.pdf",
  "sections": [
    {
      "title": "Page 1",
      "lines": ["Text preview unavailable. Use Download to inspect."]
    }
  ]
}
```

## 6. Data Model

Use the chat session id as the workspace id for v1. Add a metadata entity only when server-side tab persistence or non-session workspaces are implemented.

Recommended SQLAlchemy entity:

```python
class WorkspaceEntity(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(64), default="session")
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    root_path: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(1024), default="")
    tabs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
```

If a lighter first version is preferred, derive root paths from session ids and persist tabs in frontend localStorage first.

## 7. Frontend Architecture

Create a new feature module:

```text
frontend/src/features/file-workspace/
  components/
    file-workspace.tsx
    workspace-tabs-bar.tsx
    design-files-panel.tsx
    file-viewer.tsx
    viewers/
      html-viewer.tsx
      image-viewer.tsx
      markdown-viewer.tsx
      text-viewer.tsx
      media-viewer.tsx
      document-preview-viewer.tsx
      binary-viewer.tsx
  runtime/
    file-ops.ts
    srcdoc.ts
    exports.ts
  services/
    workspace-files.ts
  state/
    workspace-tabs-store.ts
  types.ts
```

Do not import `@open-design/contracts` or large open-design modules directly. Port only the needed types and logic.

## 8. Backend Architecture

Create:

```text
packages/aurora-serve/src/aurora_serve/files/workspace_service.py
packages/aurora-serve/src/aurora_serve/files/workspace_api.py
```

Modify:

```text
packages/aurora-serve/src/aurora_serve/router.py
packages/aurora-serve/src/aurora_serve/server.py
packages/aurora-serve/src/aurora_serve/metadata.py
packages/aurora-serve/src/aurora_serve/chat/service.py
```

Service responsibilities:

- Resolve workspace root.
- Validate paths.
- Infer MIME/kind.
- List files recursively.
- Read file bytes or stream large media.
- Write text/base64 content.
- Store uploads.
- Rename/delete files.
- Build lightweight document preview responses and return structured unsupported results when extraction is unavailable.

## 9. Migration Phases

### Phase 1: Core File API

Deliver workspace backend endpoints, path safety, kind inference, raw route, text write, multipart upload, rename, delete, and tests.

### Phase 2: Frontend API and State

Deliver TypeScript types, service functions, tab persistence, and unit tests for path encoding and file-op aggregation.

### Phase 3: File Browser and Tabs

Deliver `FileWorkspace`, sticky Files tab, open/close/reorder tabs, upload, paste, rename, delete, sort/filter, empty/error/loading states.

### Phase 4: Viewers

Deliver HTML, image, SVG, markdown, JSON, text/code, audio/video, document, and binary viewers.

### Phase 5: Chat Integration

Persist generated artifacts into the session workspace, refresh file list, auto-open primary HTML output, and replace the current in-memory artifact tabs with workspace-backed tabs.

### Phase 6: Advanced Parity

Add live artifacts, preview comments, inspect/manual edit bridge, ZIP/PDF/image export polish, and deployment flows if still desired after core usage stabilizes.

## 10. Acceptance Criteria

Core migration is accepted when:

- A new chat session has a usable workspace.
- Uploading `index.html` and `assets/logo.png` lets the HTML preview render the relative image.
- React agent HTML output appears as a workspace file and opens automatically.
- Users can list, open, rename, delete, upload, and paste files.
- Tabs persist across page refresh for the same workspace.
- HTML, image, Markdown, JSON, text/code, audio, video, PDF fallback, and binary fallback render correctly.
- Path traversal attempts are rejected by backend tests.
- Unit tests and E2E tests cover the main flows.

Advanced parity is accepted when:

- Comment/inspect/manual edit/deploy/live-artifact capabilities are implemented or explicitly rejected as out of scope.

## 11. Product Decisions

- Workspace id equals chat session id in v1. A separate `WorkspaceEntity` can be introduced later if construct/project surfaces need workspaces independent of chat.
- Workspace search is not part of v1. Phase 6 may add file-name and text search scoped to one workspace first, then global search if there is a clear product need.
- Generated artifacts use stable descriptive names when the agent supplies a title, with numeric suffixes on conflict. Timestamped names are reserved for repeated unnamed outputs.
- CODE mode tools should use the workspace root as their visible file surface only when the user is operating inside a workspace-backed session. Existing project-path behavior remains unchanged elsewhere.
- Office previews use lightweight extraction first. Full page/image rendering is a later enhancement.

## 12. Non-Goals for First Version

- Real-time collaborative editing.
- Arbitrary remote URL fetch inside previews.
- Cloud deployment.
- Full office rendering fidelity.
- Recreating open-design design-system-specific review panels.
- Recreating open-design live artifact refresh service.
