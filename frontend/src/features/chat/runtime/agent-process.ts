import type { AgentEvent, ChatMessage, ChatRunStatus } from "../types"

export type AgentProcessPhase =
  | "idle"
  | "queued"
  | "thinking"
  | "tool"
  | "artifact"
  | "finalizing"
  | "completed"
  | "failed"
  | "canceled"

export type AgentProcessNode =
  | {
      id: string
      kind: "user"
      title: string
      content: string
      timestamp?: number
    }
  | {
      id: string
      kind: "status"
      title: string
      detail?: string
      active: boolean
    }
  | {
      id: string
      kind: "thinking"
      title: string
      content: string
      active: boolean
    }
  | {
      id: string
      kind: "tool"
      title: string
      tool: string
      use: Extract<AgentEvent, { kind: "tool_use" }>
      result?: Extract<AgentEvent, { kind: "tool_result" }>
      status: "running" | "completed" | "error"
      active: boolean
      fileName?: string
    }
  | {
      id: string
      kind: "artifact"
      title: string
      detail?: string
      status: "running" | "completed" | "error"
      active: boolean
      fileName?: string
    }
  | {
      id: string
      kind: "usage"
      title: string
      detail: string
    }
  | {
      id: string
      kind: "final"
      title: string
      content: string
      active: boolean
    }

export interface AgentRunGroup {
  id: string
  title: string
  phase: AgentProcessPhase
  statusLabel: string
  active: boolean
  nodes: AgentProcessNode[]
  userMessage?: ChatMessage
  assistantMessage?: ChatMessage
  startedAt?: number
  endedAt?: number
}

export interface AgentProcessModel {
  phase: AgentProcessPhase
  statusLabel: string
  groups: AgentRunGroup[]
}

export function buildAgentProcessModel(
  messages: ChatMessage[],
  options: { streaming?: boolean } = {},
): AgentProcessModel {
  const visible = messages.filter((m) => m.role === "user" || m.role === "assistant")
  const groups: AgentRunGroup[] = []
  let current: Partial<AgentRunGroup> | null = null

  for (const message of visible) {
    if (message.role === "user") {
      if (current) groups.push(finalizeGroup(current, options.streaming))
      const id = message.id || `user-${groups.length}`
      current = {
        id,
        title: titleFromContent(asText(message.content), groups.length + 1),
        userMessage: message,
        startedAt: message.startTime ?? message.startedAt ?? message.createdAt,
        nodes: [
          {
            id: `${id}-user`,
            kind: "user",
            title: "用户请求",
            content: asText(message.content),
            timestamp: message.startTime ?? message.startedAt ?? message.createdAt,
          },
        ],
      }
      continue
    }

    if (!current) {
      current = {
        id: message.id || `assistant-${groups.length}`,
        title: "历史回复",
        nodes: [],
      }
    }
    current.assistantMessage = message
    current.endedAt = message.endTime ?? message.endedAt
    current.nodes = [
      ...(current.nodes ?? []),
      ...nodesFromAssistant(message, options.streaming === true),
    ]
  }

  if (current) groups.push(finalizeGroup(current, options.streaming))

  const activeGroup = [...groups].reverse().find((group) => group.active)
  const latest = groups[groups.length - 1]
  return {
    phase: activeGroup?.phase ?? latest?.phase ?? "idle",
    statusLabel: activeGroup?.statusLabel ?? latest?.statusLabel ?? "等待开始",
    groups,
  }
}

function finalizeGroup(group: Partial<AgentRunGroup>, streaming?: boolean): AgentRunGroup {
  const assistant = group.assistantMessage
  const latestNode = [...(group.nodes ?? [])].reverse().find((node) => node.kind !== "user")
  const active =
    isActiveRunStatus(assistant?.runStatus) ||
    (!!streaming && !!assistant && !isTerminalRunStatus(assistant.runStatus) && !assistant.endTime && !assistant.endedAt)
  const phase = phaseForGroup(assistant, latestNode, active)
  return {
    id: group.id ?? assistant?.id ?? `run-${Date.now()}`,
    title: group.title ?? "对话轮次",
    phase,
    statusLabel: statusLabelForPhase(phase, latestNode),
    active,
    nodes: group.nodes ?? [],
    userMessage: group.userMessage,
    assistantMessage: assistant,
    startedAt: group.startedAt ?? assistant?.startTime ?? assistant?.startedAt,
    endedAt: group.endedAt ?? assistant?.endTime ?? assistant?.endedAt,
  }
}

function nodesFromAssistant(message: ChatMessage, streaming: boolean): AgentProcessNode[] {
  const events = message.events ?? []
  const toolResults = new Map<string, Extract<AgentEvent, { kind: "tool_result" }>>()
  events.forEach((event) => {
    if (event.kind === "tool_result") toolResults.set(event.toolUseId, event)
  })

  const latestIndex = lastVisibleEventIndex(events)
  const nodes: AgentProcessNode[] = []

  events.forEach((event, index) => {
    const active = streaming && index === latestIndex && !message.endTime && !message.endedAt
    if (event.kind === "status") {
      nodes.push({
        id: `${message.id}-status-${index}`,
        kind: "status",
        title: event.label,
        detail: event.detail,
        active,
      })
    } else if (event.kind === "thinking") {
      nodes.push({
        id: `${message.id}-thinking-${index}`,
        kind: "thinking",
        title: "思考",
        content: event.text,
        active,
      })
    } else if (event.kind === "tool_use") {
      const result = toolResults.get(event.id)
      const isRunning = streaming && !result && !message.endTime && !message.endedAt
      nodes.push({
        id: `${message.id}-tool-${event.id}`,
        kind: "tool",
        title: toolTitle(event.name),
        tool: event.name,
        use: event,
        result,
        status: result?.isError ? "error" : isRunning ? "running" : "completed",
        active: isRunning || active,
        fileName: fileNameFromToolInput(event.input),
      })
    } else if (event.kind === "live_artifact") {
      nodes.push({
        id: `${message.id}-artifact-${event.artifactId}-${index}`,
        kind: "artifact",
        title: artifactTitle(event.title),
        detail: artifactDetail(event.action, event.refreshStatus),
        status: event.action === "deleted" ? "error" : "completed",
        active,
        fileName: fileNameFromArtifactTitle(event.title),
      })
    } else if (event.kind === "live_artifact_refresh") {
      nodes.push({
        id: `${message.id}-artifact-refresh-${event.refreshId ?? index}`,
        kind: "artifact",
        title: artifactTitle(event.title ?? event.artifactId),
        detail: refreshDetail(event),
        status: event.phase === "failed" ? "error" : event.phase === "started" ? "running" : "completed",
        active: event.phase === "started" || active,
        fileName: event.title ? fileNameFromArtifactTitle(event.title) : undefined,
      })
    } else if (event.kind === "usage") {
      nodes.push({
        id: `${message.id}-usage-${index}`,
        kind: "usage",
        title: "用量统计",
        detail: usageDetail(event),
      })
    }
  })

  const finalText = assistantText(message)
  if (finalText) {
    nodes.push({
      id: `${message.id}-final`,
      kind: "final",
      title: "最终回复",
      content: finalText,
      active: streaming && !message.endTime && !message.endedAt && latestIndex < 0,
    })
  }

  if (nodes.length === 0 && asText(message.content)) {
    nodes.push({
      id: `${message.id}-final`,
      kind: "final",
      title: "历史回复",
      content: asText(message.content),
      active: false,
    })
  }

  return nodes
}

function phaseForGroup(
  assistant: ChatMessage | undefined,
  latestNode: AgentProcessNode | undefined,
  active: boolean,
): AgentProcessPhase {
  if (assistant?.runStatus === "failed") return "failed"
  if (assistant?.runStatus === "canceled") return "canceled"
  if (!assistant) return "queued"
  if (!active) {
    const hasError = (assistant.events ?? []).some((event) => event.kind === "tool_result" && event.isError)
    return hasError ? "failed" : "completed"
  }
  if (latestNode?.kind === "tool") return "tool"
  if (latestNode?.kind === "artifact") return "artifact"
  if (latestNode?.kind === "thinking") return "thinking"
  if (latestNode?.kind === "final") return "finalizing"
  return assistant.runStatus === "queued" ? "queued" : "thinking"
}

function statusLabelForPhase(phase: AgentProcessPhase, latestNode: AgentProcessNode | undefined): string {
  if (phase === "queued") return "等待模型响应"
  if (phase === "thinking") return "AI 正在分析"
  if (phase === "tool") return latestNode?.kind === "tool" ? `正在使用 ${latestNode.tool}` : "正在调用工具"
  if (phase === "artifact") return "正在更新文件"
  if (phase === "finalizing") return "正在整理回复"
  if (phase === "failed") return "执行失败"
  if (phase === "canceled") return "已停止"
  if (phase === "completed") return "已完成"
  return "等待开始"
}

function lastVisibleEventIndex(events: AgentEvent[]): number {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.kind !== "text" && events[i]?.kind !== "raw") return i
  }
  return -1
}

function assistantText(message: ChatMessage): string {
  const content = asText(message.content).trim()
  if (content) return content
  return (message.events ?? [])
    .filter((event): event is Extract<AgentEvent, { kind: "text" }> => event.kind === "text")
    .map((event) => event.text)
    .join("")
    .trim()
}

function asText(content: ChatMessage["content"]): string {
  return typeof content === "string" ? content : ""
}

function titleFromContent(content: string, index: number): string {
  const text = content.replace(/\s+/g, " ").trim()
  if (!text) return `第 ${index} 轮对话`
  return text.length > 34 ? `${text.slice(0, 34)}...` : text
}

function isActiveRunStatus(status: ChatRunStatus | undefined): boolean {
  return status === "queued" || status === "running"
}

function isTerminalRunStatus(status: ChatRunStatus | undefined): boolean {
  return status === "succeeded" || status === "failed" || status === "canceled"
}

function toolTitle(name: string): string {
  const normalized = name.replace(/[_-]+/g, " ")
  return normalized.replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function fileNameFromToolInput(input: unknown): string | undefined {
  if (!input || typeof input !== "object") return undefined
  const record = input as Record<string, unknown>
  const value = record.file_path ?? record.filePath ?? record.path ?? record.name
  if (typeof value !== "string" || !value.trim()) return undefined
  return basename(value)
}

function fileNameFromArtifactTitle(title: string): string | undefined {
  const trimmed = title.trim()
  return trimmed.includes(".") ? basename(trimmed) : undefined
}

function basename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path
}

function artifactTitle(title: string): string {
  return title.trim() || "生成文件"
}

function artifactDetail(action: Extract<AgentEvent, { kind: "live_artifact" }>["action"], refreshStatus?: string): string {
  const actionText = action === "created" ? "已创建" : action === "updated" ? "已更新" : "已删除"
  return refreshStatus ? `${actionText} · ${refreshStatus}` : actionText
}

function refreshDetail(event: Extract<AgentEvent, { kind: "live_artifact_refresh" }>): string {
  if (event.phase === "started") return "刷新开始"
  if (event.phase === "failed") return event.error ? `刷新失败 · ${event.error}` : "刷新失败"
  return typeof event.refreshedSourceCount === "number"
    ? `刷新完成 · ${event.refreshedSourceCount} 个来源`
    : "刷新完成"
}

function usageDetail(event: Extract<AgentEvent, { kind: "usage" }>): string {
  const parts: string[] = []
  if (typeof event.inputTokens === "number") parts.push(`输入 ${event.inputTokens}`)
  if (typeof event.outputTokens === "number") parts.push(`输出 ${event.outputTokens}`)
  if (typeof event.durationMs === "number") parts.push(formatDuration(event.durationMs))
  if (typeof event.costUsd === "number") parts.push(`$${event.costUsd.toFixed(4)}`)
  return parts.join(" · ") || "已收到用量信息"
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}
