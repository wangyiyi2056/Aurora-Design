import type { AgentEvent } from "@/features/chat/types"

export type FileOpKind = "read" | "write" | "edit"
export type FileOpStatus = "running" | "done" | "error"

export interface FileOpEntry {
  path: string
  fullPath: string
  ops: FileOpKind[]
  opCounts: Record<FileOpKind, number>
  total: number
  status: FileOpStatus
}

const READ_NAMES = new Set(["Read", "read_file"])
const WRITE_NAMES = new Set(["Write", "create_file"])
const EDIT_NAMES = new Set(["Edit", "str_replace_edit", "MultiEdit", "multi_edit"])

function classify(name: string): FileOpKind | null {
  if (READ_NAMES.has(name)) return "read"
  if (WRITE_NAMES.has(name)) return "write"
  if (EDIT_NAMES.has(name)) return "edit"
  return null
}

function extractPath(input: unknown): string | null {
  if (!input || typeof input !== "object") return null
  const obj = input as { file_path?: unknown; path?: unknown }
  if (typeof obj.file_path === "string" && obj.file_path) return obj.file_path
  if (typeof obj.path === "string" && obj.path) return obj.path
  return null
}

function basename(input: string): string {
  const segments = input.split(/[\\/]/).filter(Boolean)
  return segments.at(-1) ?? input
}

function mergeStatus(a: FileOpStatus, b: FileOpStatus): FileOpStatus {
  if (a === "error" || b === "error") return "error"
  if (a === "running" || b === "running") return "running"
  return "done"
}

export function deriveFileOps(events: AgentEvent[] | undefined): FileOpEntry[] {
  if (!events?.length) return []
  const results = new Map<string, Extract<AgentEvent, { kind: "tool_result" }>>()
  for (const event of events) {
    if (event.kind === "tool_result") results.set(event.toolUseId, event)
  }

  const byPath = new Map<string, FileOpEntry>()
  for (const event of events) {
    if (event.kind !== "tool_use") continue
    const kind = classify(event.name)
    if (!kind) continue
    const fullPath = extractPath(event.input)
    if (!fullPath || fullPath === "(unnamed)") continue
    const result = results.get(event.id)
    const status: FileOpStatus = result == null ? "running" : result.isError ? "error" : "done"
    const existing = byPath.get(fullPath)
    if (existing) {
      if (!existing.ops.includes(kind)) existing.ops.push(kind)
      existing.opCounts[kind] += 1
      existing.total += 1
      existing.status = mergeStatus(existing.status, status)
      continue
    }
    const opCounts: Record<FileOpKind, number> = { read: 0, write: 0, edit: 0 }
    opCounts[kind] = 1
    byPath.set(fullPath, {
      path: basename(fullPath),
      fullPath,
      ops: [kind],
      opCounts,
      total: 1,
      status,
    })
  }
  return Array.from(byPath.values())
}
