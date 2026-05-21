import type { AgentEvent } from "@/features/chat/types"
import type { ChatMessage, MessagePart } from "@/stores/chat-store"

export function createMessageId(prefix: string): string {
  const randomId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  return `${prefix}-${randomId}`
}

export function textFromEvents(events?: AgentEvent[]): string {
  return (events ?? [])
    .filter((event) => event.kind === "text")
    .map((event) => event.text)
    .join("")
}

export function textFromMessageContent(content: ChatMessage["content"] | string | undefined): string {
  if (!content) return ""
  if (typeof content === "string") return content
  return content
    .filter((part): part is Extract<MessagePart, { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("")
}

export function resolvedMessageText(message: {
  content?: ChatMessage["content"] | string
  events?: AgentEvent[]
}): string {
  const contentText = textFromMessageContent(message.content)
  return contentText || textFromEvents(message.events)
}

export function eventsFromMessage(message: ChatMessage): AgentEvent[] {
  if (message.events?.length) return message.events
  if (typeof message.content === "string") {
    return message.content ? [{ kind: "text", text: message.content }] : []
  }

  const events: AgentEvent[] = []
  for (const part of message.content) {
    if (part.type === "text") {
      events.push({ kind: "text", text: part.text })
    } else if (part.type === "reasoning") {
      events.push({ kind: "thinking", text: part.text })
    } else if (part.type === "status") {
      events.push({ kind: "status", label: part.label, detail: part.detail })
    } else if (part.type === "tool") {
      events.push({
        kind: "tool_use",
        id: part.id,
        name: part.tool,
        input: part.state.input ?? {},
      })
      if (part.state.output || part.state.error || part.state.status === "completed") {
        events.push({
          kind: "tool_result",
          toolUseId: part.id,
          content: part.state.error ?? part.state.output ?? "",
          isError: part.state.status === "error",
        })
      }
    }
  }
  return events
}
