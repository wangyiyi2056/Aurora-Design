import type { SSEEvent } from "@/features/chat/utils/sse-parser"
import type { AgentEvent } from "@/features/chat/types"

export interface GeneratedWorkspaceArtifact {
  key: string
  name: string
  content: string
  shouldOpen: boolean
  encoding?: "utf8" | "base64"
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

export function artifactFromToolCallStartEvent(event: SSEEvent): GeneratedWorkspaceArtifact | null {
  if (event.type !== "tool_call_start") return null
  const name = normalizeToolName(event.tool_name)
  if (!isWriteToolName(name)) return null
  const input = parseToolArguments(event.arguments)
  if (!input) return null
  const filePath = stringFromRecord(input, "file_path") ?? stringFromRecord(input, "path")
  const content = stringFromRecord(input, "content")
  if (!filePath || !content) return null
  return artifactFromWrittenFile(filePath, content)
}

const LANG_TO_OUTPUT: Record<string, string> = {
  html: "html",
  htm: "html",
  markdown: "markdown",
  md: "markdown",
  json: "json",
  js: "code",
  javascript: "code",
  jsx: "code",
  ts: "code",
  typescript: "code",
  tsx: "code",
  css: "code",
  scss: "code",
  sql: "code",
  python: "code",
  py: "code",
  svg: "image",
}

const EXT_BY_LANG: Record<string, string> = {
  javascript: "js",
  typescript: "ts",
  python: "py",
}

export function artifactsFromAssistantText(text: string): GeneratedWorkspaceArtifact[] {
  const artifacts: GeneratedWorkspaceArtifact[] = []
  const usedNames = new Set<string>()

  for (const artifact of extractArtifactTags(text)) {
    artifacts.push(uniqueArtifact(artifact, usedNames))
  }

  for (const image of extractDataUrlImages(text)) {
    artifacts.push(uniqueArtifact(image, usedNames))
  }

  const fencePattern = /```([^\n`]*)\n([\s\S]*?)```/g
  let match: RegExpExecArray | null
  let index = 0
  while ((match = fencePattern.exec(text)) !== null) {
    const rawLang = match[1]?.trim().split(/\s+/)[0].toLowerCase() ?? ""
    const content = (match[2] ?? "").trim()
    if (!content) continue
    const artifact = artifactFromCodeBlock(rawLang, content, index)
    if (artifact) artifacts.push(uniqueArtifact(artifact, usedNames))
    index += 1
  }

  if (artifacts.length === 0) {
    const trimmed = text.trim()
    if (looksLikeHtml(trimmed)) {
      artifacts.push(uniqueArtifact(textArtifact("html", "HTML", trimmed), usedNames))
    }
  }

  return artifacts
}

export function artifactsFromPartialAssistantText(text: string): GeneratedWorkspaceArtifact[] {
  const artifact = extractPartialArtifactTag(text)
  return artifact ? [artifact] : []
}

export function artifactsFromAgentEvents(events: AgentEvent[] = []): GeneratedWorkspaceArtifact[] {
  const artifacts: GeneratedWorkspaceArtifact[] = []
  const usedNames = new Set<string>()

  for (const event of events) {
    if (event.kind !== "tool_use") continue
    const name = normalizeToolName(event.name)
    if (!isWriteToolName(name)) continue
    const input = event.input
    if (!isRecord(input)) continue
    const filePath = stringFromRecord(input, "file_path") ?? stringFromRecord(input, "path")
    const content = stringFromRecord(input, "content")
    if (!filePath || !content) continue
    const artifact = artifactFromWrittenFile(filePath, content)
    if (artifact) artifacts.push(uniqueArtifact(artifact, usedNames))
  }

  return artifacts
}

export function canonicalArtifactsForAssistant(
  textArtifacts: GeneratedWorkspaceArtifact[],
  eventArtifacts: GeneratedWorkspaceArtifact[],
): GeneratedWorkspaceArtifact[] {
  const all = [...eventArtifacts, ...textArtifacts]
  const html = all.filter((artifact) => isHtmlArtifact(artifact))
  if (html.length > 1) {
    const bestHtml = [...html].sort((a, b) => b.content.length - a.content.length)[0]
    return [
      bestHtml,
      ...all.filter((artifact) => !isHtmlArtifact(artifact)),
    ].filter((artifact): artifact is GeneratedWorkspaceArtifact => Boolean(artifact))
  }
  return textArtifacts.length > 0 ? textArtifacts : eventArtifacts
}

function isHtmlArtifact(artifact: GeneratedWorkspaceArtifact): boolean {
  return artifact.name.toLowerCase().endsWith(".html") || looksLikeHtml(artifact.content)
}

function artifactFromWrittenFile(filePath: string, content: string): GeneratedWorkspaceArtifact | null {
  const extension = extensionFromPath(filePath)
  if (!extension) return null
  const outputType = outputTypeFromExtension(extension, content)
  if (!outputType && !looksLikeHtml(content)) return null
  const basename = filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? titleForAssistantOutput(outputType ?? "text")
  const relativePath = safeRelativeWorkspacePath(filePath)
  return {
    key: `tool-write:${filePath}:${hashString(content)}`,
    name: relativePath ?? `generated/${safeFileStem(basename)}.${extension}`,
    content,
    shouldOpen: (outputType ?? "html") === "html" || (outputType ?? "") === "image",
    encoding: "utf8",
  }
}

function safeRelativeWorkspacePath(filePath: string): string | null {
  const normalized = filePath.replace(/\\/g, "/").trim()
  if (!normalized || normalized.startsWith("/") || /^[A-Za-z]:\//.test(normalized)) return null
  const parts = normalized.split("/").filter(Boolean)
  if (parts.length === 0 || parts.some((part) => part === "." || part === "..")) return null
  return parts.map(safePathPart).join("/")
}

function safePathPart(value: string): string {
  const part = value
    .trim()
    .replace(/[\\/:*?"<>|#%{}^~[\]`]+/g, "-")
    .replace(/^\.+/, "")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100)
    .trim()
  return part || "artifact"
}

function normalizeToolName(name: string): string {
  return name.replace(/\s+/g, "").toLowerCase()
}

function isWriteToolName(name: string): boolean {
  return ["write", "filewritetool", "writefile", "write_file"].includes(name)
}

function parseToolArguments(raw: string | undefined): Record<string, unknown> | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return isRecord(parsed) ? parsed : null
  } catch {
    return null
  }
}

function stringFromRecord(record: Record<string, unknown>, key: string): string | null {
  const value = record[key]
  return typeof value === "string" ? value : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function extensionFromPath(filePath: string): string | null {
  const name = filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? ""
  const dot = name.lastIndexOf(".")
  if (dot <= 0 || dot === name.length - 1) return null
  return name.slice(dot + 1).toLowerCase()
}

function outputTypeFromExtension(extension: string, content: string): string | null {
  if (extension === "html" || extension === "htm") return "html"
  if (extension === "md" || extension === "markdown") return "markdown"
  if (extension === "json") return "json"
  if (extension === "svg") return "image"
  if (["js", "jsx", "ts", "tsx", "css", "scss", "sql", "py"].includes(extension)) return "code"
  if (looksLikeHtml(content)) return "html"
  return null
}

function artifactFromCodeBlock(
  lang: string,
  content: string,
  index: number,
): GeneratedWorkspaceArtifact | null {
  const outputType = LANG_TO_OUTPUT[lang]
  if (!outputType) {
    if (looksLikeHtml(content)) return textArtifact("html", "HTML", content)
    return null
  }
  if (outputType === "image" && lang === "svg") {
    return {
      key: `assistant:${lang}:${hashString(content)}`,
      name: `generated/${index === 0 ? "Image" : `Image ${index + 1}`}.svg`,
      content,
      shouldOpen: true,
      encoding: "utf8",
    }
  }

  const title = outputType === "html" ? "HTML" : titleForAssistantOutput(outputType)
  const ext = EXT_BY_LANG[lang] ?? EXT_BY_OUTPUT[outputType] ?? (lang || "txt")
  return {
    key: `assistant:${lang || outputType}:${hashString(content)}`,
    name: `generated/${safeFileStem(title)}.${ext}`,
    content,
    shouldOpen: outputType === "html",
    encoding: "utf8",
  }
}

function textArtifact(outputType: string, title: string, content: string): GeneratedWorkspaceArtifact {
  const ext = EXT_BY_OUTPUT[outputType] ?? "txt"
  return {
    key: `assistant:${outputType}:${hashString(content)}`,
    name: `generated/${safeFileStem(title)}.${ext}`,
    content,
    shouldOpen: outputType === "html",
    encoding: "utf8",
  }
}

function titleForAssistantOutput(outputType: string): string {
  if (outputType === "markdown") return "Markdown"
  if (outputType === "json") return "JSON"
  if (outputType === "code") return "Code"
  if (outputType === "text") return "Text"
  return defaultTitle(outputType)
}

function extractArtifactTags(text: string): GeneratedWorkspaceArtifact[] {
  const artifacts: GeneratedWorkspaceArtifact[] = []
  const pattern = /<artifact\b([^>]*)>([\s\S]*?)<\/artifact>/gi
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    const attrs = parseArtifactAttrs(match[1] ?? "")
    const content = (match[2] ?? "").trim()
    if (!content) continue
    const outputType = outputTypeFromArtifact(attrs.type, content)
    const ext = EXT_BY_OUTPUT[outputType] ?? extensionFromArtifactType(attrs.type) ?? "txt"
    const title = attrs.title || attrs.identifier || titleForAssistantOutput(outputType)
    artifacts.push({
      key: `artifact:${attrs.identifier || attrs.title || outputType}:${hashString(content)}`,
      name: `generated/${safeFileStem(title)}.${ext}`,
      content,
      shouldOpen: outputType === "html" || outputType === "image",
      encoding: "utf8",
    })
  }
  return artifacts
}

function extractPartialArtifactTag(text: string): GeneratedWorkspaceArtifact | null {
  const open = /<artifact\b([^>]*)>/gi
  let match: RegExpExecArray | null
  let latest: RegExpExecArray | null = null
  while ((match = open.exec(text)) !== null) latest = match
  if (!latest || latest.index === undefined) return null
  const start = latest.index + latest[0].length
  const close = text.indexOf("</artifact>", start)
  const content = (close === -1 ? text.slice(start) : text.slice(start, close)).trim()
  if (!content) return null
  const attrs = parseArtifactAttrs(latest[1] ?? "")
  const outputType = outputTypeFromArtifact(attrs.type, content)
  const ext = EXT_BY_OUTPUT[outputType] ?? extensionFromArtifactType(attrs.type) ?? "txt"
  const title = attrs.title || attrs.identifier || titleForAssistantOutput(outputType)
  return {
    key: `artifact-live:${attrs.identifier || attrs.title || outputType}:${hashString(content)}`,
    name: `generated/${safeFileStem(title)}.${ext}`,
    content,
    shouldOpen: outputType === "html" || outputType === "image",
    encoding: "utf8",
  }
}

function parseArtifactAttrs(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {}
  const pattern = /([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(raw)) !== null) {
    const key = match[1]
    if (key) attrs[key] = match[2] ?? match[3] ?? ""
  }
  return attrs
}

function outputTypeFromArtifact(type: string | undefined, content: string): string {
  const normalized = (type ?? "").toLowerCase()
  if (normalized.includes("html")) return "html"
  if (normalized.includes("markdown") || normalized.endsWith("/md")) return "markdown"
  if (normalized.includes("json")) return "json"
  if (normalized.includes("svg")) return "image"
  if (looksLikeHtml(content)) return "html"
  return "text"
}

function extensionFromArtifactType(type: string | undefined): string | null {
  const normalized = (type ?? "").toLowerCase()
  if (normalized.includes("svg")) return "svg"
  if (normalized.includes("markdown")) return "md"
  if (normalized.includes("json")) return "json"
  if (normalized.includes("html")) return "html"
  return null
}

function extractDataUrlImages(text: string): GeneratedWorkspaceArtifact[] {
  const artifacts: GeneratedWorkspaceArtifact[] = []
  const pattern = /!\[([^\]]*)\]\((data:image\/([a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\r\n]+))\)/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    const alt = match[1]?.trim() || "image"
    const format = normalizeImageFormat(match[3] ?? "png")
    const body = (match[4] ?? "").replace(/\s+/g, "")
    if (!body) continue
    artifacts.push({
      key: `assistant:image:${hashString(match[2] ?? body)}`,
      name: `generated/${safeFileStem(alt)}.${format}`,
      content: body,
      shouldOpen: true,
      encoding: "base64",
    })
  }
  return artifacts
}

function uniqueArtifact(
  artifact: GeneratedWorkspaceArtifact,
  usedNames: Set<string>,
): GeneratedWorkspaceArtifact {
  if (!usedNames.has(artifact.name)) {
    usedNames.add(artifact.name)
    return artifact
  }
  const dot = artifact.name.lastIndexOf(".")
  const base = dot >= 0 ? artifact.name.slice(0, dot) : artifact.name
  const ext = dot >= 0 ? artifact.name.slice(dot) : ""
  let counter = 2
  let next = `${base}-${counter}${ext}`
  while (usedNames.has(next)) {
    counter += 1
    next = `${base}-${counter}${ext}`
  }
  usedNames.add(next)
  return { ...artifact, name: next }
}

function normalizeImageFormat(format: string): string {
  const lower = format.toLowerCase()
  if (lower === "jpeg") return "jpg"
  if (lower === "svg+xml") return "svg"
  return lower || "png"
}

function looksLikeHtml(content: string): boolean {
  return /<!doctype\s+html/i.test(content) || /<html[\s>]/i.test(content)
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
