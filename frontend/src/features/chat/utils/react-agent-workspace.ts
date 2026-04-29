export type ReactAgentStepStatus = "pending" | "running" | "completed" | "error"

export type ReactAgentOutputType =
  | "code"
  | "text"
  | "markdown"
  | "table"
  | "chart"
  | "json"
  | "error"
  | "thought"
  | "html"
  | "image"

export interface ReactAgentStep {
  id: string
  step?: number
  title: string
  detail?: string
  phase?: string
  status: ReactAgentStepStatus
  action?: string
  actionInput?: unknown
  type: "read" | "skill" | "sql" | "html" | "code" | "other"
}

export interface ReactAgentOutput {
  output_type: ReactAgentOutputType
  content: unknown
}

export interface ReactAgentArtifact {
  id: string
  type: "file" | "table" | "chart" | "image" | "code" | "markdown" | "summary" | "html"
  name: string
  content: unknown
  createdAt: number
  downloadable?: boolean
  stepId?: string
}

export type ReactAgentPanelView = "execution" | "files" | "summary" | "html-preview" | "image-preview"

export type ReactAgentSSEEvent =
  | { type: "step.start"; id: string; step?: number; title: string; detail?: string; phase?: string }
  | { type: "step.meta"; id: string; thought?: string; action?: string; action_input?: unknown; title?: string }
  | { type: "step.chunk"; id: string; output_type: ReactAgentOutputType; content: unknown }
  | { type: "step.done"; id: string; status: "done" | "failed" | "completed" | "error" }
  | { type: "final"; content: string }
  | { type: "done" }

export interface ReactAgentSnapshot {
  steps: ReactAgentStep[]
  outputs: Record<string, ReactAgentOutput[]>
  activeStepId: string | null
  summary: string
  isDone: boolean
}

function mapActionToStepType(action = "", title = ""): ReactAgentStep["type"] {
  const value = `${action} ${title}`.toLowerCase()
  if (value.includes("html")) return "html"
  if (value.includes("sql") || value.includes("duckdb")) return "sql"
  if (value.includes("skill") || value.includes("learn")) return "skill"
  if (value.includes("file") || value.includes("read")) return "read"
  if (value.includes("code")) return "code"
  return "other"
}

function normalizeDoneStatus(status: string): ReactAgentStepStatus {
  if (status === "done" || status === "completed") return "completed"
  if (status === "failed" || status === "error") return "error"
  return "completed"
}

export function parseReactAgentSSELine(line: string): ReactAgentSSEEvent | null {
  const trimmed = line.trim()
  if (!trimmed.startsWith("data:")) return null
  const raw = trimmed.slice(5).trim()
  if (!raw || raw === "[DONE]") return null
  try {
    return JSON.parse(raw) as ReactAgentSSEEvent
  } catch {
    return null
  }
}

export class ReactAgentSSEState {
  private steps: ReactAgentStep[] = []
  private outputs: Record<string, ReactAgentOutput[]> = {}
  private activeStepId: string | null = null
  private summary = ""
  private isDone = false

  processEvent(event: ReactAgentSSEEvent) {
    switch (event.type) {
      case "step.start":
        this.upsertStep({
          id: event.id,
          step: event.step,
          title: event.title,
          detail: event.detail,
          phase: event.phase,
          status: "running",
          type: mapActionToStepType("", event.title),
        })
        this.outputs[event.id] ||= []
        this.activeStepId = event.id
        break
      case "step.meta":
        this.steps = this.steps.map((step) =>
          step.id === event.id
            ? {
                ...step,
                title: event.title || step.title,
                action: event.action || step.action,
                actionInput: event.action_input ?? step.actionInput,
                detail: event.thought || step.detail,
                type: mapActionToStepType(event.action || step.action, event.title || step.title),
              }
            : step
        )
        this.activeStepId = event.id
        break
      case "step.chunk":
        this.outputs[event.id] = [
          ...(this.outputs[event.id] || []),
          { output_type: event.output_type, content: event.content },
        ]
        this.activeStepId = event.id
        break
      case "step.done":
        this.steps = this.steps.map((step) =>
          step.id === event.id ? { ...step, status: normalizeDoneStatus(event.status) } : step
        )
        break
      case "final":
        this.summary = event.content
        break
      case "done":
        this.isDone = true
        break
    }
  }

  getSnapshot(): ReactAgentSnapshot {
    return {
      steps: [...this.steps],
      outputs: { ...this.outputs },
      activeStepId: this.activeStepId,
      summary: this.summary,
      isDone: this.isDone,
    }
  }

  private upsertStep(next: ReactAgentStep) {
    const existing = this.steps.findIndex((step) => step.id === next.id)
    if (existing >= 0) {
      this.steps = this.steps.map((step) => (step.id === next.id ? { ...step, ...next } : step))
      return
    }
    this.steps = [
      ...this.steps.map((step) => (step.status === "running" ? { ...step, status: "completed" as const } : step)),
      next,
    ]
  }
}

export function buildArtifactsFromExecution(input: {
  steps: Pick<ReactAgentStep, "id" | "title" | "status" | "type">[]
  outputs: Record<string, ReactAgentOutput[]>
  summary?: string
}): ReactAgentArtifact[] {
  const artifacts: ReactAgentArtifact[] = []
  const createdAt = Date.now()
  for (const step of input.steps) {
    for (const [index, output] of (input.outputs[step.id] || []).entries()) {
      if (output.output_type === "html") {
        const content = output.content as { html?: string; content?: string; title?: string } | string
        const html = typeof content === "string" ? content : content.html || content.content || ""
        const title = typeof content === "string" ? "Report" : content.title || "Report"
        artifacts.push({
          id: `${step.id}-html-${index}`,
          type: "html",
          name: `${title}.html`,
          content: html,
          createdAt,
          stepId: step.id,
          downloadable: true,
        })
      }
      if (output.output_type === "code") {
        artifacts.push({
          id: `${step.id}-code-${index}`,
          type: "code",
          name: `${step.title || "code"}.sql`,
          content: output.content,
          createdAt,
          stepId: step.id,
          downloadable: true,
        })
      }
    }
  }
  if (input.summary) {
    artifacts.push({
      id: "summary",
      type: "summary",
      name: "摘要",
      content: input.summary,
      createdAt,
    })
  }
  return artifacts
}

export function getPreferredPanelView(artifacts: ReactAgentArtifact[]): ReactAgentPanelView {
  if (artifacts.some((artifact) => artifact.type === "html")) return "html-preview"
  if (artifacts.length > 0) return "files"
  return "execution"
}
