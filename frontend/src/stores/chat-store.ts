import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

const MAX_MESSAGES = 100

interface ChatState {
  messages: ChatMessage[]
  input: string
  loading: boolean
  model: string
  setMessages: (messages: ChatMessage[]) => void
  addMessage: (message: ChatMessage) => void
  appendToLastMessage: (chunk: string) => void
  setInput: (input: string) => void
  setLoading: (loading: boolean) => void
  setModel: (model: string) => void
  resetChat: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [
        {
          role: "system",
          content: "Welcome to ChatBI. Ask anything about data or general questions.",
        },
      ],
      input: "",
      loading: false,
      model: "gemma-4-e4b-it-8bit",
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
      resetChat: () =>
        set({
          messages: [
            {
              role: "system",
              content: "Welcome to ChatBI. Ask anything about data or general questions.",
            },
          ],
          input: "",
          loading: false,
        }),
    }),
    { name: "chatbi-chat-store" }
  )
)
