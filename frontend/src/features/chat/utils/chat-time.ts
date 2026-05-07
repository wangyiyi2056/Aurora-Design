import type { ChatMessage } from "@/stores/chat-store"

export function messageTime(message: ChatMessage): number | undefined {
  if (message.role === "assistant") {
    return message.startTime ?? message.endTime
  }
  return message.startTime ?? message.endTime
}

export function exactDateTime(ts: number): string {
  return new Date(ts).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function relativeTimeLong(ts: number): string {
  const diff = Math.max(0, Date.now() - ts)
  const min = 60_000
  const hr = 60 * min
  const day = 24 * hr
  if (diff < min) return "刚刚"
  if (diff < hr) return `${Math.floor(diff / min)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hr)} 小时前`
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`
  return new Date(ts).toLocaleDateString()
}
