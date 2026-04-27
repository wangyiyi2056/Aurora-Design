import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

export interface SessionMeta {
  id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
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
}

const initialSystemMessage: ChatMessage = {
  role: "system",
  content: "Welcome to ChatBI. Ask anything about data or general questions.",
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [initialSystemMessage],
      input: "",
      loading: false,
      model: "kimi-for-coding",
      sessionId: null,
      sessions: [],
      sessionsLoading: false,

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
            msgs[msgs.length - 1] = { ...last, content: last.content + chunk }
          } else {
            msgs.push({ role: "assistant", content: chunk })
          }
          if (msgs.length > MAX_MESSAGES) {
            msgs.splice(0, msgs.length - MAX_MESSAGES)
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
        }),

      resetToNewChat: () =>
        set({
          messages: [initialSystemMessage],
          input: "",
          loading: false,
          sessionId: null,
        }),
    }),
    { name: "chatbi-chat-store" }
  )
)
