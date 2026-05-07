import type { APIChatMessage, ContentPart } from "@/services/chat"
import type { ByokConfig } from "@/stores/provider-store"
import { parseSseFrame } from "@/providers/sse"

export interface StreamHandlers {
  onDelta: (delta: string) => void
  onDone: (content: string) => void
  onError: (error: Error) => void
}

export async function streamProxyEndpoint(
  endpoint: string,
  cfg: ByokConfig,
  history: APIChatMessage[],
  signal: AbortSignal,
  handlers: StreamHandlers,
): Promise<void> {
  if (!cfg.apiKey.trim()) {
    handlers.onError(new Error("Missing API key"))
    return
  }
  if (!cfg.model.trim()) {
    handlers.onError(new Error("Missing model"))
    return
  }

  const { systemPrompt, messages } = normalizeMessages(history)
  let acc = ""

  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        baseUrl: cfg.baseUrl,
        apiKey: cfg.apiKey,
        model: cfg.model,
        systemPrompt,
        messages,
        maxTokens: null,
        apiVersion: cfg.apiVersion,
      }),
      signal,
    })

    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => "")
      handlers.onError(new Error(`proxy ${resp.status}: ${text || "no body"}`))
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      while (true) {
        const match = buffer.match(/\r?\n\r?\n/)
        if (!match || match.index === undefined) break
        const frame = buffer.slice(0, match.index)
        buffer = buffer.slice(match.index + match[0].length)
        const parsed = parseSseFrame(frame)
        if (!parsed || parsed.kind !== "event") continue

        if (parsed.event === "delta") {
          const text = String(parsed.data.delta ?? parsed.data.text ?? "")
          if (text) {
            acc += text
            handlers.onDelta(text)
          }
          continue
        }

        if (parsed.event === "error") {
          handlers.onError(new Error(proxyErrorMessage(parsed.data)))
          return
        }

        if (parsed.event === "end") {
          handlers.onDone(acc)
          return
        }
      }
    }

    handlers.onDone(acc)
  } catch (error) {
    if ((error as Error).name === "AbortError") return
    handlers.onError(error instanceof Error ? error : new Error(String(error)))
  }
}

function normalizeMessages(history: APIChatMessage[]): {
  systemPrompt?: string
  messages: { role: string; content: string }[]
} {
  let systemPrompt: string | undefined
  const messages: { role: string; content: string }[] = []

  for (const message of history) {
    const content = stringifyContent(message.content)
    if (!content.trim()) continue
    if (message.role === "system") {
      systemPrompt = systemPrompt ? `${systemPrompt}\n\n${content}` : content
      continue
    }
    if (message.role === "tool") continue
    messages.push({ role: message.role, content })
  }

  return { systemPrompt, messages }
}

function stringifyContent(content: APIChatMessage["content"]): string {
  if (typeof content === "string") return content
  return content
    .map((part: ContentPart) => {
      if (part.type === "text") return part.text ?? ""
      if (part.type === "image_url") return part.image_url?.url ? `[image] ${part.image_url.url}` : ""
      if (part.type === "file_url") return part.file_url?.url ? `[file] ${part.file_url.file_name}: ${part.file_url.url}` : ""
      return ""
    })
    .filter(Boolean)
    .join("\n")
}

function proxyErrorMessage(data: Record<string, unknown>): string {
  const nested = data.error
  if (nested && typeof nested === "object" && "message" in nested) {
    const message = (nested as { message?: unknown }).message
    if (typeof message === "string" && message) return message
  }
  return String(data.message ?? "proxy error")
}
