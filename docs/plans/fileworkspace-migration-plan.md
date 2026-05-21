# Fileworkspace Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or execute this plan task-by-task with verification after each phase.

**Goal:** Add an Aurora fileworkspace for previewing and managing HTML, images, Markdown, JSON, text/code, media, PDFs, and generated chat artifacts.

**Architecture:** Reimplement open-design's fileworkspace contract in Aurora's stack. Backend file operations live in FastAPI services and routes; frontend workspace UI lives under a new `features/file-workspace` module and integrates with chat sessions.

**Tech Stack:** FastAPI, SQLAlchemy, Python pathlib/mimetypes, React 18, TypeScript, Zustand, Vite, Vitest, Playwright.

---

## Source References

- open-design UI: `/Users/wyl/Desktop/github/open-design/apps/web/src/components/FileWorkspace.tsx`
- open-design browser panel: `/Users/wyl/Desktop/github/open-design/apps/web/src/components/DesignFilesPanel.tsx`
- open-design viewer: `/Users/wyl/Desktop/github/open-design/apps/web/src/components/FileViewer.tsx`
- open-design file ops: `/Users/wyl/Desktop/github/open-design/apps/web/src/runtime/file-ops.ts`
- open-design routes: `/Users/wyl/Desktop/github/open-design/apps/daemon/src/project-routes.ts`
- Aurora file service: `/Users/wyl/Desktop/Aurora-Design/packages/aurora-serve/src/aurora_serve/files/service.py`
- Aurora file API: `/Users/wyl/Desktop/Aurora-Design/packages/aurora-serve/src/aurora_serve/files/api.py`
- Aurora chat workspace candidate: `/Users/wyl/Desktop/Aurora-Design/frontend/src/features/chat/components/react-agent-workspace.tsx`

## Phase 0: Spec and Scope Lock

- [x] Create full feature spec at `specs/fileworkspace/spec.md`.
- [x] Keep existing `specs/aurora-platform-documentation` as current-state documentation.
- [x] Confirm first implementation target is the 85% core scope: file API, tabs, browser, viewers, and chat artifact integration.
- [x] Decide whether workspace id equals session id for v1. V1 uses chat session id directly.

## Phase 1: Backend Workspace Service

**Files:**

- Create: `packages/aurora-serve/src/aurora_serve/files/workspace_service.py`
- Create: `packages/aurora-serve/src/aurora_serve/files/workspace_api.py`
- Modify: `packages/aurora-serve/src/aurora_serve/router.py`
- Modify: `packages/aurora-serve/src/aurora_serve/server.py`
- Optional modify: `packages/aurora-serve/src/aurora_serve/metadata.py`
- Test: `tests/serve/test_workspace_files_api.py`

**Steps:**

- [x] Add `WorkspaceFile` response helpers with `name`, `path`, `type`, `size`, `mtime`, `kind`, and `mime`.
- [x] Implement `workspace_root(workspace_id)` under `data/workspaces/{workspace_id}`.
- [x] Implement `resolve_workspace_path()` with absolute path, traversal, URL-encoded traversal, and symlink escape protection.
- [x] Implement MIME/kind inference.
- [x] Implement recursive file listing.
- [x] Implement raw file reading with `FileResponse`.
- [ ] Implement audio/video range support if `FileResponse` is insufficient for reliable seeking.
- [x] Implement text/base64 write endpoint.
- [x] Implement multipart upload endpoint.
- [x] Implement rename endpoint.
- [x] Implement delete endpoint.
- [x] Wire router under `/api/v1/workspaces`.
- [x] Add backend tests for list, write, raw read, upload, rename, delete, nested paths, MIME/kind, and traversal rejection.

**Verification:**

```bash
uv run pytest tests/serve/test_workspace_files_api.py
```

## Phase 2: Frontend Types, Services, and State

**Files:**

- Create: `frontend/src/features/file-workspace/types.ts`
- Create: `frontend/src/features/file-workspace/services/workspace-files.ts`
- Create: `frontend/src/features/file-workspace/runtime/file-ops.ts`
- Create: `frontend/src/features/file-workspace/state/workspace-tabs-store.ts`
- Test: `frontend/src/features/file-workspace/runtime/file-ops.test.ts`
- Test: `frontend/src/features/file-workspace/services/workspace-files.test.ts`

**Steps:**

- [x] Define `WorkspaceFileKind`, `WorkspaceFile`, `WorkspaceTabsState`, and upload result types.
- [x] Add `fetchWorkspaceFiles(workspaceId)`.
- [x] Add `workspaceRawUrl(workspaceId, path)` with per-segment encoding.
- [x] Add `fetchWorkspaceFileText`.
- [x] Add `writeWorkspaceTextFile`.
- [x] Add `uploadWorkspaceFiles`.
- [x] Add `renameWorkspaceFile`.
- [x] Add `deleteWorkspaceFile`.
- [x] Port and adapt open-design `deriveFileOps` for Aurora `AgentEvent`.
- [x] Add localStorage-backed tab state keyed by workspace id.

**Verification:**

```bash
cd frontend && pnpm test -- file-workspace
```

## Phase 3: File Workspace Shell and Browser

**Files:**

- Create: `frontend/src/features/file-workspace/components/file-workspace.tsx`
- Create: `frontend/src/features/file-workspace/components/workspace-tabs-bar.tsx`
- Create: `frontend/src/features/file-workspace/components/design-files-panel.tsx`
- Modify only as needed: `frontend/src/features/chat/components/react-agent-workspace.tsx`

**Steps:**

- [x] Build `FileWorkspace` container that accepts `workspaceId`, `files`, `loading`, `onRefreshFiles`, and optional `openRequest`.
- [x] Add sticky Files tab.
- [ ] Add open/close/reorder active file tabs.
- [x] Add open/close active file tabs. Reorder remains Phase 6 polish.
- [x] Add file list sorted by mtime/name. Grouping and sort controls remain Phase 6 polish.
- [x] Add file upload button and drag/drop upload.
- [x] Add simple new-file flow.
- [x] Add row actions for open, rename, delete. Download is available in viewers.
- [ ] Add multi-select and batch delete with confirmation.
- [x] Add loading, empty, and unsupported states.
- [x] Ensure all buttons use lucide icons and accessible labels.

**Verification:**

```bash
cd frontend && pnpm test
cd frontend && pnpm build
```

## Phase 4: Viewers and Preview Runtime

**Files:**

- Create: `frontend/src/features/file-workspace/components/file-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/html-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/image-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/markdown-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/text-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/media-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/document-preview-viewer.tsx`
- Create: `frontend/src/features/file-workspace/components/viewers/binary-viewer.tsx`
- Create: `frontend/src/features/file-workspace/runtime/srcdoc.ts`
- Create: `frontend/src/features/file-workspace/runtime/exports.ts`

**Steps:**

- [x] Implement viewer dispatch by `WorkspaceFile.kind`.
- [x] Implement HTML viewer with sandbox iframe, cache busting, refresh, viewport presets, open in new tab, and download. Zoom remains Phase 6 polish.
- [ ] Resolve relative HTML assets through a `<base href>` pointing at the workspace raw file directory.
- [x] Implement image/SVG viewer.
- [x] Implement Markdown viewer with source-style rendering.
- [x] Implement text/code/JSON source viewer.
- [x] Implement audio/video viewer with raw URLs.
- [x] Implement document/binary fallback with metadata and download/open action.

**Verification:**

```bash
cd frontend && pnpm test
cd frontend && pnpm build
```

Manual browser verification:

- Upload `index.html` referencing `assets/logo.png`.
- Open `index.html`.
- Confirm relative image renders in iframe.
- Switch desktop/tablet/mobile viewport.
- Download HTML.

## Phase 5: Chat and React Agent Integration

**Files:**

- Modify: `packages/aurora-serve/src/aurora_serve/chat/schema.py`
- Modify: `packages/aurora-serve/src/aurora_serve/chat/service.py`
- Modify: `packages/aurora-serve/src/aurora_serve/chat/api.py`
- Modify: `frontend/src/features/chat/utils/react-agent-workspace.ts`
- Modify: `frontend/src/features/chat/components/react-agent-workspace.tsx`
- Modify: `frontend/src/features/chat/pages/chat-page.tsx`

**Steps:**

- [x] Add `workspace_id` to chat/session response metadata or derive it from session id in frontend.
- [x] When React agent outputs HTML/code/json/markdown/text chunks, persist them to the workspace using the frontend workspace service.
- [x] Add generated file metadata through workspace file listing.
- [x] Refresh workspace files after chat stream completion.
- [x] Auto-open generated HTML artifacts.
- [x] Add `FileWorkspace` as the chat right-side workspace panel.
- [ ] Show file operation summaries above assistant outputs where events include Read/Write/Edit.

**Verification:**

```bash
uv run pytest tests/serve/test_chat_api.py tests/serve/test_workspace_files_api.py
cd frontend && pnpm test
cd frontend && pnpm build
```

Manual verification:

- Start a chat session.
- Run a prompt that produces HTML.
- Confirm the HTML appears in workspace files.
- Refresh the page.
- Confirm tabs and files still load.

## Phase 6: E2E and Polish

**Files:**

- Create: `frontend/e2e/file-workspace.spec.ts` or extend existing Playwright setup.
- Modify: `frontend/src/i18n/content.ts` and locale files as needed.

**Steps:**

- [ ] Add i18n keys for all visible workspace actions and states.
- [ ] Add Playwright test for upload HTML plus relative image preview.
- [ ] Add Playwright test for generated HTML artifact opening in workspace.
- [ ] Add Playwright test for rename/delete tab synchronization.
- [ ] Audit responsive layout at 390px, 820px, 1440px.
- [ ] Fix focus states and accessible labels.
- [ ] Run full frontend and backend test suites.

**Verification:**

```bash
uv run pytest
cd frontend && pnpm test
cd frontend && pnpm e2e
cd frontend && pnpm build
```

## Phase 7: Optional Advanced Parity

Only start this phase after the core workflow is stable.

- [ ] Preview comments and drawing overlays.
- [ ] Inspect/manual-edit iframe bridge.
- [ ] ZIP export with handoff manifest.
- [ ] Image snapshot export.
- [ ] Live artifact refresh service.
- [ ] Vercel/Cloudflare deployment.
- [ ] Office preview rendering beyond text fallback.

## Risk Notes

- The largest risk is path safety. Backend tests must cover every unsafe path form before UI integration.
- The second largest risk is over-porting open-design's monolithic viewer. Split viewers in Aurora to keep the code maintainable.
- HTML preview can become a security footgun. Keep iframe sandboxing and raw file origin behavior explicit.
- Do not make open-design contracts a runtime dependency of Aurora.
- Do not mix this future feature into `specs/aurora-platform-documentation` unless that documentation is re-scoped from "actual implementation" to "roadmap".
