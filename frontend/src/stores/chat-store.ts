import { create } from "zustand"
import { persist } from "zustand/middleware"

// === Message Part Types (adapted from DB-GPT) ===

export type ToolStatus = "pending" | "running" | "completed" | "error"

export interface ToolPart {
  id: string
  type: "tool"
  tool: string
  callID?: string
  state: {
    status: ToolStatus
    input?: Record<string, unknown>
    output?: string
    error?: string
    metadata?: Record<string, unknown>
  }
}

export interface TextPart {
  id: string
  type: "text"
  text: string
}

export interface ReasoningPart {
  id: string
  type: "reasoning"
  text: string
}

export type MessagePart = ToolPart | TextPart | ReasoningPart

// === Chat Message ===

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string | MessagePart[] // backward compatible
  startTime?: number
  endTime?: number
  thinkingContent?: string
}

export interface SessionMeta {
  id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
}

// === Debug Pipeline ===

export interface DebugPipelineStep {
  id: string
  name: string
  description: string
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  timestamp?: number
  duration?: number
  detail?: string
}

const MAX_MESSAGES = 100

interface ChatState {
  messages: ChatMessage[]
  input: string
  loading: boolean
  model: string
  sessionId: string | null
  sessions: SessionMeta[]
  sessionsLoading: boolean
  streamingParts: MessagePart[]
  streamingStatus: string | null
  abortController: AbortController | null
  debugPipelineSteps: DebugPipelineStep[]
  debugPipelineEnabled: boolean

  setMessages: (messages: ChatMessage[]) => void
  addMessage: (message: ChatMessage) => void
  appendToLastMessage: (chunk: string) => void
  setInput: (input: string) => void
  setLoading: (loading: boolean) => void
  setModel: (model: string) => void
  setSessionId: (id: string | null) => void
  setSessions: (sessions: SessionMeta[]) => void
  setSessionsLoading: (loading: boolean) => void
  loadSessionMessages: (messages: ChatMessage[]) => void
  resetChat: () => void
  resetToNewChat: () => void
  setStreamingParts: (parts: MessagePart[]) => void
  setStreamingStatus: (status: string | null) => void
  finalizeStreamingMessage: () => void
  setAbortController: (controller: AbortController | null) => void
  abortStreaming: () => void
  updatePipelineStep: (step: Partial<DebugPipelineStep> & { id: string }) => void
  resetPipelineSteps: () => void
  setDebugPipelineEnabled: (enabled: boolean) => void
}

const initialSystemMessage: ChatMessage = {
  role: "system",
  content: "Welcome to Aurora Design. Ask anything about data or general questions.",
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [initialSystemMessage],
      input: "",
      loading: false,
      model: "gpt-4o-mini",
      sessionId: null,
      sessions: [],
      sessionsLoading: false,
      streamingParts: [],
      streamingStatus: null,
      abortController: null,
      debugPipelineSteps: [],
      debugPipelineEnabled: false,

      setMessages: (messages) => set({ messages }),
      addMessage: (message) =>
        set((state) => ({
          messages: state.messages.slice(-MAX_MESSAGES).concat(message),
        })),
      appendToLastMessage: (chunk) =>
        set((state) => {
          const msgs = [...state.messages]
          const last = msgs[msgs.length - 1]
          if (last && last.role === "assistant") {
            // Handle both string and MessagePart[] content - immutable updates
            if (typeof last.content === "string") {
              msgs[msgs.length - 1] = { ...last, content: last.content + chunk }
            } else {
              // Immutable update: create new parts array with updated text
              // TypeScript knows content is MessagePart[] here
              const existingParts = last.content as MessagePart[]
              const existingTextPart = existingParts.find(p => p.type === "text")

              const parts = existingParts.map(p => {
                if (p.type === "text" && p.id === existingTextPart?.id) {
                  return { ...p, text: (p as TextPart).text + chunk }
                }
                return p
              })

              // If no text part exists, add one
              if (!existingTextPart) {
                parts.push({ id: `text-${Date.now()}`, type: "text", text: chunk } as TextPart)
              }
              msgs[msgs.length - 1] = { ...last, content: parts }
            }
          } else {
            msgs.push({ role: "assistant", content: chunk })
          }
          // Immutable: use slice instead of splice
          if (msgs.length > MAX_MESSAGES) {
            return { messages: msgs.slice(-MAX_MESSAGES) }
          }
          return { messages: msgs }
        }),
      setInput: (input) => set({ input }),
      setLoading: (loading) => set({ loading }),
      setModel: (model) => set({ model }),
      setSessionId: (id) => set({ sessionId: id }),
      setSessions: (sessions) => set({ sessions }),
      setSessionsLoading: (loading) => set({ sessionsLoading: loading }),

      loadSessionMessages: (messages) =>
        set({
          messages: [
            initialSystemMessage,
            ...messages.slice(-MAX_MESSAGES),
          ],
          loading: false,
        }),

      resetChat: () =>
        set({
          messages: [initialSystemMessage],
          input: "",
          loading: false,
          sessionId: null,
          streamingParts: [],
          streamingStatus: null,
          abortController: null,
          debugPipelineSteps: [],
        }),

      resetToNewChat: () =>
        set({
          messages: [initialSystemMessage],
          input: "",
          loading: false,
          sessionId: null,
          streamingParts: [],
          streamingStatus: null,
          abortController: null,
          debugPipelineSteps: [],
        }),

      setStreamingParts: (parts) => set({ streamingParts: parts }),
      setStreamingStatus: (status) => set({ streamingStatus: status }),
      finalizeStreamingMessage: () =>
        set((state) => {
          const parts = state.streamingParts
          if (parts.length === 0) return { streamingParts: [], streamingStatus: null }

          // Extract final text content from parts
          const textParts = parts.filter(p => p.type === "text")
          const finalContent = textParts.map(p => p.text).join("")

          return {
            messages: state.messages.slice(-MAX_MESSAGES).concat({
              role: "assistant",
              content: parts.length > 0 ? parts : finalContent,
              endTime: Date.now(),
            }),
            streamingParts: [],
            streamingStatus: null,
          }
        }),

      setAbortController: (controller) => set({ abortController: controller }),

      abortStreaming: () =>
        set((state) => {
          if (state.abortController) {
            state.abortController.abort()
          }
          return {
            abortController: null,
            loading: false,
            streamingParts: [],
            streamingStatus: null,
          }
        }),

      updatePipelineStep: (step) =>
        set((state) => {
          const existing = state.debugPipelineSteps.find((s) => s.id === step.id)
          if (existing) {
            // Update existing step
            const updated: DebugPipelineStep = {
              ...existing,
              ...step,
              duration:
                step.status === "completed" && existing.timestamp
                  ? Date.now() - existing.timestamp
                  : step.duration,
            }
            return {
              debugPipelineSteps: state.debugPipelineSteps.map((s) =>
                s.id === step.id ? updated : s
              ),
            }
          }
          // Add new step with all required fields
          const newStep: DebugPipelineStep = {
            id: step.id,
            name: step.name || step.id,
            description: step.description || "",
            status: step.status || "pending",
            timestamp: step.status === "running" ? Date.now() : undefined,
            duration: step.duration,
            detail: step.detail,
          }
          return {
            debugPipelineSteps: [...state.debugPipelineSteps, newStep],
          }
        }),

      resetPipelineSteps: () => set({ debugPipelineSteps: [] }),

      setDebugPipelineEnabled: (enabled) => set({ debugPipelineEnabled: enabled }),
    }),
    { name: "aurora-chat-store" }
  )
)
