import type { SSEEvent } from "@/features/chat/utils/sse-parser"

export interface GeneratedWorkspaceArtifact {
  key: string
  name: string
  content: string
  shouldOpen: boolean
}

const EXT_BY_OUTPUT: Record<string, string> = {
  html: "html",
  code: "sql",
  json: "json",
  markdown: "md",
  text: "txt",
}

export function artifactFromStreamEvent(event: SSEEvent): GeneratedWorkspaceArtifact | null {
  if (event.type !== "step.chunk") return null
  if (!["html", "code", "json", "markdown", "text"].includes(event.output_type)) return null

  const content = extractContent(event.content, event.output_type)
  if (!content.trim()) return null

  const title = extractTitle(event.content) || defaultTitle(event.output_type)
  const ext = EXT_BY_OUTPUT[event.output_type] ?? "txt"
  const name = `generated/${safeFileStem(title)}.${ext}`
  const key = `${event.id}:${event.output_type}:${hashString(content)}`

  return {
    key,
    name,
    content,
    shouldOpen: event.output_type === "html",
  }
}

function extractContent(content: unknown, outputType: string): string {
  if (typeof content === "string") return content
  if (!content || typeof content !== "object") return ""
  const record = content as Record<string, unknown>
  if (typeof record.html === "string") return record.html
  if (typeof record.content === "string") return record.content
  if (typeof record.markdown === "string") return record.markdown
  if (typeof record.text === "string") return record.text
  if (outputType === "json" || outputType === "code") return JSON.stringify(record, null, 2)
  return ""
}

function extractTitle(content: unknown): string | null {
  if (!content || typeof content !== "object") return null
  const title = (content as Record<string, unknown>).title
  return typeof title === "string" ? title : null
}

function defaultTitle(outputType: string): string {
  if (outputType === "html") return "Report"
  if (outputType === "code") return "Query"
  return outputType
}

export function safeFileStem(value: string): string {
  const stem = value
    .trim()
    .replace(/\.[A-Za-z0-9]+$/, "")
    .replace(/[\\/:*?"<>|#%{}^~[\]`]+/g, "-")
    .replace(/\s+/g, " ")
    .replace(/^\.+/, "")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .trim()
  return stem || "artifact"
}

function hashString(value: string): string {
  let hash = 5381
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index)
  }
  return (hash >>> 0).toString(36)
}
