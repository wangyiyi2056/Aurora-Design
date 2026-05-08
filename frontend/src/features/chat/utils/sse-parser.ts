/**
 * Chat SSE Parser State
 *
 * Parses SSE events from aurora backend and converts them to MessagePart[]
 * for rendering in the UI.
 *
 * SSE Event Types (from aurora backend):
 * - text_start: Start of text content
 * - text_delta: Streaming text chunk
 * - text_end: End of text content
 * - tool_call_start: Tool execution started
 * - tool_call_result: Tool execution completed
 * - reasoning_start: Thinking/reasoning started
 * - reasoning_end: Thinking/reasoning ended
 *
 * Adapted from DB-GPT's react-sse-parser.ts architecture pattern.
 */

import type { MessagePart, ToolPart, TextPart, ReasoningPart, StatusPart, ToolStatus, DebugPipelineStep } from "@/stores/chat-store"

// SSE Event Types
export interface SSETextStartEvent {
  type: "text_start"
}

export interface SSETextDeltaEvent {
  type: "text_delta"
  content: string
}

export interface SSETextEndEvent {
  type: "text_end"
  finish_reason?: string
  id?: string
  model?: string
  usage?: Record<string, unknown>
}

export interface SSEToolCallStartEvent {
  type: "tool_call_start"
  tool_name: string
  arguments?: string
  id?: string
}

export interface SSEToolCallResultEvent {
  type: "tool_call_result"
  tool_name: string
  content: string
  id?: string
}

export interface SSEReasoningStartEvent {
  type: "reasoning_start"
}

export interface SSEReasoningDeltaEvent {
  type: "reasoning_delta"
  content: string
}

export interface SSEReasoningEndEvent {
  type: "reasoning_end"
}

export interface SSEStatusEvent {
  type: "status"
  label: string
  detail?: string
}

export interface SSEPipelineStepEvent {
  type: "pipeline_step"
  step_id: string
  step_name: string
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  detail?: string
}

export type SSEEvent =
  | SSETextStartEvent
  | SSETextDeltaEvent
  | SSETextEndEvent
  | SSEToolCallStartEvent
  | SSEToolCallResultEvent
  | SSEReasoningStartEvent
  | SSEReasoningDeltaEvent
  | SSEReasoningEndEvent
  | SSEStatusEvent
  | SSEPipelineStepEvent

// Internal state for tracking streaming content
interface ToolState {
  id: string
  tool: string
  status: ToolStatus
  input?: Record<string, unknown>
  output?: string
  error?: string
}

/**
 * Chat SSE Parser State
 * Manages the state of the streaming chat session
 */
export class ChatSSEState {
  private parts: MessagePart[] = []
  private textBuffer: string = ""
  private textPartId: string | null = null
  private reasoningBuffer: string = ""
  private reasoningPartId: string | null = null
  private toolOrder: string[] = []
  private statusLabel: string | null = null
  private lastStatusPartId: string | null = null
  private startTime: number
  private endTime?: number
  private isDone: boolean = false

  constructor() {
    this.startTime = Date.now()
  }

  /**
   * Process an SSE event and update internal state
   */
  processEvent(event: SSEEvent): void {
    switch (event.type) {
      case "text_start":
        this.handleTextStart(event)
        break
      case "text_delta":
        this.handleTextDelta(event)
        break
      case "text_end":
        this.handleTextEnd(event)
        break
      case "tool_call_start":
        this.handleToolCallStart(event)
        break
      case "tool_call_result":
        this.handleToolCallResult(event)
        break
      case "reasoning_start":
        this.handleReasoningStart(event)
        break
      case "reasoning_delta":
        this.handleReasoningDelta(event)
        break
      case "reasoning_end":
        this.handleReasoningEnd(event)
        break
      case "status":
        this.handleStatus(event)
        break
      case "pipeline_step":
        // Pipeline step events are handled separately in use-chat-stream
        break
    }
  }

  private handleTextStart(_: SSETextStartEvent): void {
    this.textBuffer = ""
    this.textPartId = `text-${Date.now()}`
    this.parts.push({
      id: this.textPartId,
      type: "text",
      text: "",
    } as TextPart)
  }

  private handleTextDelta(event: SSETextDeltaEvent): void {
    if (!this.textPartId) {
      this.handleTextStart({ type: "text_start" })
    }
    this.textBuffer += event.content
    this.parts = this.parts.map((part) =>
      part.type === "text" && part.id === this.textPartId
        ? { ...part, text: this.textBuffer }
        : part
    )
  }

  private handleTextEnd(_: SSETextEndEvent): void {
    if (this.textPartId) {
      this.parts = this.textBuffer.trim()
        ? this.parts.map((part) =>
            part.type === "text" && part.id === this.textPartId
              ? { ...part, text: this.textBuffer }
              : part
          )
        : this.parts.filter((part) => part.id !== this.textPartId)
    }
    this.textPartId = null
    this.endTime = Date.now()
    this.isDone = true
  }

  private handleToolCallStart(event: SSEToolCallStartEvent): void {
    const toolId = event.id || `tool-${Date.now()}`
    const tool: ToolState = {
      id: toolId,
      tool: this.mapToolName(event.tool_name),
      status: "running",
      input: event.arguments ? parseToolArguments(event.arguments) : undefined,
    }
    this.toolOrder.push(toolId)

    // Add tool part immediately to show running status
    this.parts.push({
      id: toolId,
      type: "tool",
      tool: tool.tool,
      state: {
        status: "running",
        input: tool.input,
      },
    } as ToolPart)
  }

  private handleToolCallResult(event: SSEToolCallResultEvent): void {
    const requestedToolId = event.id || this.toolOrder[this.toolOrder.length - 1]
    const existingTool = this.parts.find(
      (p) => p.type === "tool" && p.id === requestedToolId
    ) as ToolPart | undefined

    if (!existingTool) {
      // Tool call without start - create one
      this.handleToolCallStart({
        type: "tool_call_start",
        tool_name: event.tool_name,
        id: event.id,
      })
    }

    const toolId = event.id || requestedToolId

    // Replace the tool part with updated state (immutable)
    this.parts = this.parts.map(p => {
      if (p.type === "tool" && p.id === toolId) {
        return {
          ...p,
          state: {
            ...p.state,
            status: "completed",
            output: event.content.length > 200
              ? event.content.slice(0, 200) + "..."
              : event.content,
          },
        }
      }
      return p
    })
  }

  private handleReasoningStart(_: SSEReasoningStartEvent): void {
    this.reasoningBuffer = ""
    this.reasoningPartId = null
  }

  private handleReasoningDelta(event: SSEReasoningDeltaEvent): void {
    if (!event.content) return
    this.reasoningBuffer += event.content

    if (!this.reasoningPartId) {
      this.reasoningPartId = `reasoning-${Date.now()}`
      this.parts.unshift({
        id: this.reasoningPartId,
        type: "reasoning",
        text: this.reasoningBuffer,
      } as ReasoningPart)
      return
    }

    this.parts = this.parts.map((part) =>
      part.type === "reasoning" && part.id === this.reasoningPartId
        ? { ...part, text: this.reasoningBuffer }
        : part
    )
  }

  private handleReasoningEnd(_: SSEReasoningEndEvent): void {
    // Backward compatibility for older streams that only flush reasoning at end.
    if (this.reasoningBuffer.trim() && !this.reasoningPartId) {
      this.parts.unshift({
        id: `reasoning-${Date.now()}`,
        type: "reasoning",
        text: this.reasoningBuffer,
      } as ReasoningPart)
    }
  }

  private handleStatus(event: SSEStatusEvent): void {
    this.statusLabel = event.detail ? `${event.label}: ${event.detail}` : event.label
    const existing = this.lastStatusPartId
      ? this.parts.find((part) => part.type === "status" && part.id === this.lastStatusPartId) as StatusPart | undefined
      : undefined

    if (existing && existing.label === event.label) {
      this.parts = this.parts.map((part) =>
        part.type === "status" && part.id === existing.id
          ? { ...part, detail: event.detail }
          : part
      )
      return
    }

    const id = `status-${Date.now()}-${this.parts.length}`
    this.lastStatusPartId = id
    this.parts.push({
      id,
      type: "status",
      label: event.label,
      detail: event.detail,
    } as StatusPart)
  }

  /**
   * Map backend tool names to display-friendly names
   */
  private mapToolName(toolName: string): string {
    const toolMap: Record<string, string> = {
      data_analysis: "analyze",
      sql_query: "query",
      python_execute: "execute",
      excel_analysis: "excel",
      chart_generation: "chart",
    }
    return toolMap[toolName.toLowerCase()] || toolName.toLowerCase()
  }

  /**
   * Convert current state to MessagePart array
   */
  toMessageParts(): MessagePart[] {
    return [...this.parts]
  }

  /**
   * Get final text content
   */
  getFinalContent(): string {
    return this.textBuffer
  }

  /**
   * Check if stream is complete
   */
  isComplete(): boolean {
    return this.isDone
  }

  /**
   * Check if still working (has running tools or not done)
   */
  isWorking(): boolean {
    if (this.isDone) return false
    // Check for running tools
    const runningTool = this.parts.find(p => p.type === "tool" && p.state.status === "running")
    return runningTool !== undefined || !this.isDone
  }

  /**
   * Get start time
   */
  getStartTime(): number {
    return this.startTime
  }

  /**
   * Get end time (if complete)
   */
  getEndTime(): number | undefined {
    return this.endTime
  }

  /**
   * Get current status text for display
   */
  getCurrentStatus(): string {
    const runningTool = this.parts.find(p => p.type === "tool" && p.state.status === "running")
    if (runningTool && runningTool.type === "tool") {
      return `Executing ${runningTool.tool}...`
    }
    if (this.statusLabel) return this.statusLabel
    if (this.isDone) return "Completed"
    return "Thinking..."
  }
}

/**
 * Parse a single SSE data line
 */
export function parseSSELine(line: string): SSEEvent | null {
  // Remove 'data:' prefix. Some endpoints include a space, some do not.
  const dataPrefix = "data:"
  if (!line.startsWith(dataPrefix)) {
    return null
  }

  const jsonStr = line.slice(dataPrefix.length).trim()
  if (!jsonStr || jsonStr === "[DONE]") {
    return null
  }

  try {
    return JSON.parse(jsonStr) as SSEEvent
  } catch {
    // Log parse errors only in development environment
    if (process.env.NODE_ENV === "development") {
      console.warn("[SSE Parser] Failed to parse event:", jsonStr)
    }
    return null
  }
}

/**
 * Parse multiple SSE lines (split by \n)
 */
export function parseSSEChunk(chunk: string): SSEEvent[] {
  const events: SSEEvent[] = []
  const lines = chunk.split("\n")

  for (const line of lines) {
    const trimmedLine = line.trim()
    if (trimmedLine.startsWith("data:")) {
      const event = parseSSELine(trimmedLine)
      if (event) {
        events.push(event)
      }
    }
  }

  return events
}

/**
 * Extract pipeline step events from SSE events
 */
export function extractPipelineSteps(events: SSEEvent[]): DebugPipelineStep[] {
  return events
    .filter((e) => e.type === "pipeline_step")
    .map((e) => {
      const step = e as SSEPipelineStepEvent
      return {
        id: step.step_id,
        name: step.step_name,
        description: "",
        status: step.status,
        detail: step.detail,
      }
    })
}

/**
 * Create a new Chat SSE state instance
 */
export function createChatSSEState(): ChatSSEState {
  return new ChatSSEState()
}

function parseToolArguments(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    // Keep opaque tool arguments visible when they are not JSON.
  }
  return { arguments: value }
}
