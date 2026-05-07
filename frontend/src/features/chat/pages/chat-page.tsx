import { useEffect } from "react"
import { ChatPane } from "@/features/chat/components/chat-pane"
import { sendChatStream } from "@/features/chat/hooks/use-chat-stream"
import type {
  AgentEvent,
  ChatAttachment as PaneChatAttachment,
  ChatCommentAttachment,
  ChatMessage as PaneChatMessage,
} from "@/features/chat/types"
import { createSession, loadSession } from "@/services/chat"
import type { APIChatMessage, ContentPart } from "@/services/chat"
import { useProviderStore } from "@/stores/provider-store"
import { useChatStore } from "@/stores/chat-store"

export default function ChatPage() {
  const {
    messages,
    loading,
    model,
    sessionId,
    streamingParts,
    addMessage,
    setLoading,
    setSessionId,
    loadSessionMessages,
    abortStreaming,
    resetToNewChat,
  } = useChatStore()
  const providerMode = useProviderStore((s) => s.mode)
  const byok = useProviderStore((s) => s.byok)
  const selectedAgentId = useProviderStore((s) => s.selectedAgentId)
  const agentModels = useProviderStore((s) => s.agentModels)

  const activeAgentId =
    providerMode === "daemon"
      ? selectedAgentId || (model === "claude" || model === "codex" ? model : "")
      : ""
  const activeAgentChoice = agentModels[activeAgentId] ?? {}
  const inlineModelConfig =
    providerMode === "api"
      ? {
          model_name: byok.model,
          base_url: byok.baseUrl,
          api_key: byok.apiKey,
          model_type: byok.protocol,
          api_version: byok.apiVersion,
        }
      : activeAgentId
        ? {
            model_name:
              activeAgentChoice.model && activeAgentChoice.model !== "default"
                ? activeAgentChoice.model
                : activeAgentId,
            base_url: activeAgentId,
            api_key: "",
            model_type: "daemon",
          }
        : undefined
  const requestModel = providerMode === "api" ? byok.model || model : activeAgentId || model

  useEffect(() => {
    if (sessionId && messages.length <= 1 && messages[0]?.role === "system") {
      loadSession(sessionId)
        .then((res) => {
          const msgs = res.messages
            .filter((m) => m.type === "user" || m.type === "assistant")
            .map((m) => ({
              role: (m.type === "user" ? "user" : "assistant") as "user" | "assistant",
              content: m.content,
            }))
          if (msgs.length > 0) {
            loadSessionMessages(msgs)
          }
        })
        .catch(() => {
          // Session not found or error: start fresh.
        })
    }
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const toPaneMessage = (
    msg: (typeof messages)[number],
    index: number
  ): PaneChatMessage | null => {
    if (msg.role === "system") return null
    const createdAt = msg.startTime ?? msg.endTime ?? Date.now()
    if (typeof msg.content === "string") {
      return {
        id: `${msg.role}-${index}-${createdAt}`,
        role: msg.role,
        content: msg.content,
        createdAt,
        startedAt: msg.startTime,
        endedAt: msg.endTime,
      }
    }

    const events: AgentEvent[] = []
    let text = ""
    for (const part of msg.content) {
      if (part.type === "text") {
        text += part.text
        events.push({ kind: "text", text: part.text })
      } else if (part.type === "reasoning") {
        events.push({ kind: "thinking", text: part.text })
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
    return {
      id: `${msg.role}-${index}-${createdAt}`,
      role: msg.role,
      content: text,
      events,
      createdAt,
      startedAt: msg.startTime,
      endedAt: msg.endTime,
    }
  }

  const paneMessages = messages
    .map(toPaneMessage)
    .filter((msg): msg is PaneChatMessage => msg !== null)

  if (loading && streamingParts.length > 0) {
    const streaming = toPaneMessage(
      {
        role: "assistant",
        content: streamingParts,
        startTime: Date.now(),
      },
      paneMessages.length
    )
    if (streaming) paneMessages.push(streaming)
  }

  const sendFromPane = async (
    prompt: string,
    paneAttachments: PaneChatAttachment[],
    _commentAttachments: ChatCommentAttachment[]
  ) => {
    if (!prompt.trim() || loading) return
    const question = prompt.trim()
    const contentParts: ContentPart[] = [
      ...paneAttachments.map((att) => ({
        type: "file_url" as const,
        file_url: { url: att.path, file_name: att.name },
      })),
      { type: "text" as const, text: question },
    ]

    const existingSystem = messages.find((m) => m.role === "system")?.content || ""
    const storeMessages = messages
      .filter((m) => m.role !== "system")
      .map((m) => ({
        role: m.role as "user" | "assistant" | "system",
        content:
          typeof m.content === "string"
            ? m.content
            : m.content
                .filter((p) => p.type === "text")
                .map((p) => ({ type: "text" as const, text: (p as { text: string }).text })),
      }))

    const requestMessages: APIChatMessage[] = [
      { role: "system", content: typeof existingSystem === "string" ? existingSystem : "" },
      ...storeMessages,
      { role: "user", content: contentParts },
    ]

    addMessage({ role: "user", content: question, startTime: Date.now() })
    setLoading(true)

    let currentSessionId = sessionId
    if (!currentSessionId) {
      try {
        const { session_id } = await createSession()
        currentSessionId = session_id
        setSessionId(session_id)
      } catch {
        addMessage({ role: "system", content: "⚠️ 无法创建会话，对话不会被保存" })
      }
    }

    sendChatStream({
      messages: requestMessages,
      model: requestModel,
      modelConfig: inlineModelConfig,
      session_id: currentSessionId,
    })
  }

  return (
    <div className="h-[calc(100vh-48px)]">
      <ChatPane
        messages={paneMessages}
        streaming={loading}
        error={null}
        projectId={sessionId}
        projectFiles={[]}
        onEnsureProject={async () => {
          if (sessionId) return sessionId
          const { session_id } = await createSession()
          setSessionId(session_id)
          return session_id
        }}
        onSend={sendFromPane}
        onStop={abortStreaming}
        conversations={[
          {
            id: sessionId ?? "current",
            title: "当前对话",
            updatedAt: Date.now(),
          },
        ]}
        activeConversationId={sessionId ?? "current"}
        onSelectConversation={() => undefined}
        onDeleteConversation={() => undefined}
        onNewConversation={resetToNewChat}
      />
    </div>
  )
}
