import { create } from "zustand"

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

interface ChatState {
  messages: ChatMessage[]
  input: string
  loading: boolean
  model: string
  setMessages: (messages: ChatMessage[]) => void
  addMessage: (message: ChatMessage) => void
  setInput: (input: string) => void
  setLoading: (loading: boolean) => void
  setModel: (model: string) => void
  resetChat: () => void
}

export const useChatStore = create<ChatState>((set) => ({
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
    set((state) => ({ messages: [...state.messages, message] })),
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
}))
