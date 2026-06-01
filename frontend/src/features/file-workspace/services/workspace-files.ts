import type { WorkspaceFile, WorkspaceUploadResult } from "../types"

export function workspaceRawUrl(workspaceId: string, filePath: string): string {
  const safePath = filePath
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/")
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/raw/${safePath}`
}

export function workspacePreviewPdfUrl(workspaceId: string, filePath: string): string {
  const safePath = filePath
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/")
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files/${safePath}/preview/pdf`
}

export async function fetchWorkspaceFilePreviewInfo(
  workspaceId: string,
  filePath: string,
): Promise<{ previewAvailable: boolean } | null> {
  const safePath = filePath
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/")
  try {
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files/${safePath}/preview`)
    if (!resp.ok) return null
    return (await resp.json()) as { previewAvailable: boolean }
  } catch {
    return null
  }
}

export function workspaceFileUrl(workspaceId: string, filePath: string): string {
  return workspaceRawUrl(workspaceId, filePath)
}

export function workspaceArchiveUrl(workspaceId: string, root = ""): string {
  const base = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/archive`
  return root ? `${base}?root=${encodeURIComponent(root)}` : base
}

export async function fetchWorkspaceFiles(workspaceId: string): Promise<WorkspaceFile[]> {
  try {
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files`)
    if (!resp.ok) return []
    const json = (await resp.json()) as { files?: WorkspaceFile[] }
    return json.files ?? []
  } catch {
    return []
  }
}

export async function fetchWorkspaceFileText(
  workspaceId: string,
  filePath: string,
  options?: { cacheBustKey?: string | number; cache?: RequestCache },
): Promise<string | null> {
  const url = workspaceRawUrl(workspaceId, filePath)
  const requestUrl =
    options?.cacheBustKey == null
      ? url
      : `${url}?cacheBust=${encodeURIComponent(String(options.cacheBustKey))}`
  try {
    const init: RequestInit = {}
    if (options?.cache) init.cache = options.cache
    const resp = await fetch(requestUrl, init)
    if (!resp.ok) return null
    return await resp.text()
  } catch {
    return null
  }
}

export async function writeWorkspaceTextFile(
  workspaceId: string,
  name: string,
  content: string,
  options: { overwrite?: boolean; encoding?: "utf8" | "base64" } = {},
): Promise<WorkspaceFile | null> {
  try {
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        content,
        encoding: options.encoding ?? "utf8",
        overwrite: options.overwrite ?? true,
      }),
    })
    if (!resp.ok) return null
    const json = (await resp.json()) as { file?: WorkspaceFile }
    return json.file ?? null
  } catch {
    return null
  }
}

export async function uploadWorkspaceFiles(
  workspaceId: string,
  files: File[],
  baseDir = "",
): Promise<WorkspaceUploadResult> {
  if (files.length === 0) return { files: [], failed: [] }
  try {
    const form = new FormData()
    for (const file of files) form.append("files", file)
    if (baseDir) form.append("base_dir", baseDir)
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/upload`, {
      method: "POST",
      body: form,
    })
    if (!resp.ok) {
      const error = `upload failed (${resp.status})`
      return { files: [], failed: files.map((file) => ({ name: file.name, error })), error }
    }
    const json = (await resp.json()) as WorkspaceUploadResult
    return { files: json.files ?? [], failed: json.failed ?? [] }
  } catch {
    const error = "upload request failed"
    return { files: [], failed: files.map((file) => ({ name: file.name, error })), error }
  }
}

export async function renameWorkspaceFile(
  workspaceId: string,
  from: string,
  to: string,
): Promise<{ oldName: string; newName: string; file: WorkspaceFile }> {
  const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from, to }),
  })
  if (!resp.ok) throw new Error(`rename failed (${resp.status})`)
  return (await resp.json()) as { oldName: string; newName: string; file: WorkspaceFile }
}

export async function deleteWorkspaceFile(workspaceId: string, filePath: string): Promise<boolean> {
  try {
    const resp = await fetch(workspaceRawUrl(workspaceId, filePath), { method: "DELETE" })
    return resp.ok
  } catch {
    return false
  }
}
