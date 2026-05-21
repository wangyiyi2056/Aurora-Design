import {
  Activity,
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileText,
  Loader2,
  MessageSquare,
  Zap,
} from "lucide-react"

import type { ChatMessage } from "../types"
import type { ToolPart } from "@/stores/chat-store"
import {
  buildAgentProcessModel,
  type AgentProcessNode,
  type AgentProcessPhase,
} from "../runtime/agent-process"
import { ToolCard } from "./tool-card"

interface AgentProcessViewProps {
  messages: ChatMessage[]
  streaming: boolean
  projectFileNames?: Set<string>
  onRequestOpenFile?: (name: string) => void
}

export function AgentProcessView({
  messages,
  streaming,
  projectFileNames,
  onRequestOpenFile,
}: AgentProcessViewProps) {
  const model = buildAgentProcessModel(messages, { streaming })
  const hasRuns = model.groups.length > 0

  return (
    <div className="agent-process-panel" data-testid="agent-process-view">
      <div className="agent-process-status" data-phase={model.phase}>
        <div className="agent-process-status-icon">
          <PhaseIcon phase={model.phase} active={streaming} />
        </div>
        <div>
          <div className="agent-process-status-label">{model.statusLabel}</div>
          <div className="agent-process-status-detail">
            {hasRuns ? `${model.groups.length} 轮对话 · ${countNodes(model.groups.flatMap((g) => g.nodes))} 个节点` : "开始对话后，这里会展示 AI 的执行过程"}
          </div>
        </div>
      </div>

      {!hasRuns ? (
        <div className="agent-process-empty">
          <Activity className="h-6 w-6" />
          <span>开始对话后，这里会展示 AI 的执行过程</span>
        </div>
      ) : (
        <div className="agent-process-runs">
          {model.groups.map((group, index) => (
            <details
              key={group.id}
              className={`agent-process-run${group.active ? " active" : ""}`}
              data-phase={group.phase}
              data-testid={`agent-process-run-${index}`}
              open={index === model.groups.length - 1}
            >
              <summary className="agent-process-run-head">
                <div>
                  <span className="agent-process-run-kicker">第 {index + 1} 轮</span>
                  <h3>{group.title}</h3>
                </div>
                <span className="agent-process-run-meta">
                  <span className="agent-process-run-status">{group.statusLabel}</span>
                  <ChevronDown className="agent-process-run-chevron h-3.5 w-3.5" />
                </span>
              </summary>
              <div className="agent-process-timeline">
                {group.nodes.map((node) => (
                  <ProcessNode
                    key={node.id}
                    node={node}
                    projectFileNames={projectFileNames}
                    onRequestOpenFile={onRequestOpenFile}
                  />
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  )
}

function ProcessNode({
  node,
  projectFileNames,
  onRequestOpenFile,
}: {
  node: AgentProcessNode
  projectFileNames?: Set<string>
  onRequestOpenFile?: (name: string) => void
}) {
  if (node.kind === "tool") {
    return (
      <div className={`agent-process-node ${node.kind}${node.active ? " active" : ""}`}>
        <NodeIcon node={node} />
        <div className="agent-process-node-body">
          <ToolCard
            part={toolPartFromNode(node)}
            runStreaming={node.status === "running"}
            projectFileNames={projectFileNames}
            onRequestOpenFile={onRequestOpenFile}
            defaultOpen={node.status === "error" || node.active}
            compact
          />
        </div>
      </div>
    )
  }

  const canOpen =
    "fileName" in node &&
    !!node.fileName &&
    !!onRequestOpenFile &&
    (projectFileNames ? projectFileNames.has(node.fileName) : true)

  return (
    <div className={`agent-process-node ${node.kind}${isActiveNode(node) ? " active" : ""}`}>
      <NodeIcon node={node} />
      <div className="agent-process-node-body">
        <div className="agent-process-node-card">
          <div className="agent-process-node-title-row">
            <strong>{node.title}</strong>
            {isActiveNode(node) ? <span className="agent-process-live">进行中</span> : null}
          </div>
          {node.kind === "status" && node.detail ? (
            <p>{node.detail}</p>
          ) : null}
          {node.kind === "thinking" ? (
            <details>
              <summary>
                查看思考摘要
                <ChevronDown className="h-3.5 w-3.5" />
              </summary>
              <p>{node.content}</p>
            </details>
          ) : null}
          {node.kind === "user" || node.kind === "final" ? (
            <p>{compactText(node.content)}</p>
          ) : null}
          {node.kind === "artifact" ? (
            <div className="agent-process-file-row">
              <span>{node.detail}</span>
              {node.fileName ? (
                <button
                  type="button"
                  className="agent-process-file-btn"
                  disabled={!canOpen}
                  onClick={() => node.fileName && onRequestOpenFile?.(node.fileName)}
                  title={canOpen ? `打开 ${node.fileName}` : node.fileName}
                >
                  <FileText className="h-3.5 w-3.5" />
                  {node.fileName}
                </button>
              ) : null}
            </div>
          ) : null}
          {node.kind === "usage" ? <p>{node.detail}</p> : null}
        </div>
      </div>
    </div>
  )
}

function PhaseIcon({ phase, active }: { phase: AgentProcessPhase; active: boolean }) {
  if (active && (phase === "thinking" || phase === "tool" || phase === "artifact" || phase === "finalizing")) {
    return <Loader2 className="h-4 w-4 animate-spin" />
  }
  if (phase === "completed") return <CheckCircle2 className="h-4 w-4" />
  if (phase === "failed" || phase === "canceled") return <AlertCircle className="h-4 w-4" />
  if (phase === "tool") return <Zap className="h-4 w-4" />
  if (phase === "queued") return <Clock className="h-4 w-4" />
  return <Bot className="h-4 w-4" />
}

function NodeIcon({ node }: { node: AgentProcessNode }) {
  const icon =
    node.kind === "user" ? (
      <MessageSquare className="h-3.5 w-3.5" />
    ) : node.kind === "tool" ? (
      <Zap className="h-3.5 w-3.5" />
    ) : node.kind === "artifact" ? (
      <FileText className="h-3.5 w-3.5" />
    ) : node.kind === "usage" ? (
      <Activity className="h-3.5 w-3.5" />
    ) : node.kind === "final" ? (
      <CheckCircle2 className="h-3.5 w-3.5" />
    ) : (
      <Bot className="h-3.5 w-3.5" />
    )

  return <div className="agent-process-node-icon">{icon}</div>
}

function compactText(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (normalized.length <= 240) return normalized
  return `${normalized.slice(0, 240)}...`
}

function countNodes(nodes: AgentProcessNode[]): number {
  return nodes.filter((node) => node.kind !== "user").length
}

function isActiveNode(node: AgentProcessNode): boolean {
  return "active" in node && node.active
}

function toolPartFromNode(node: Extract<AgentProcessNode, { kind: "tool" }>): ToolPart {
  return {
    id: node.use.id,
    type: "tool",
    tool: node.use.name,
    callID: node.use.id,
    state: {
      status: node.status,
      input:
        node.use.input && typeof node.use.input === "object" && !Array.isArray(node.use.input)
          ? (node.use.input as Record<string, unknown>)
          : { value: node.use.input },
      output: node.result?.isError ? undefined : node.result?.content,
      error: node.result?.isError ? node.result.content : undefined,
    },
  }
}
