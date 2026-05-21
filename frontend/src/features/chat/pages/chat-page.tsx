import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ChatPane } from "@/features/chat/components/chat-pane"
import { FileWorkspace } from "@/features/file-workspace/components/file-workspace"
import { ResizableDivider } from "@/components/ui/resizable-divider"
import { artifactFromStreamEvent } from "@/features/file-workspace/runtime/generated-artifacts"
import { fetchWorkspaceFiles, writeWorkspaceTextFile } from "@/features/file-workspace/services/workspace-files"
import type { WorkspaceFile } from "@/features/file-workspace/types"
import { sendChatStream } from "@/features/chat/hooks/use-chat-stream"
import type {
  AgentEvent,
  ChatAttachment as PaneChatAttachment,
  ChatCommentAttachment,
  ChatMessage as PaneChatMessage,
} from "@/features/chat/types"
import { createSession, deleteSession, listSessions, loadSession } from "@/services/chat"
import type { APIChatMessage, ContentPart } from "@/services/chat"
import { useProviderStore } from "@/stores/provider-store"
import { useChatStore, type SessionMeta } from "@/stores/chat-store"

export default function ChatPage() {
  const {
    messages,
    loading,
    model,
    sessionId,
    sessions,
    addMessage,
    setLoading,
    setSessionId,
    setSessions,
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
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [openRequest, setOpenRequest] = useState<{ name: string; nonce: number } | null>(null)
  const generatedArtifactKeys = useRef<Set<string>>(new Set())
  const pendingArtifactWrites = useRef<Promise<unknown>[]>([])
  const messageLoadSeq = useRef(0)
  const sessionListLoadSeq = useRef(0)
  const messagesSessionId = useRef<string | null>(null)
  const creatingConversation = useRef(false)

  const refreshWorkspaceFiles = useCallback(async (workspaceId = sessionId) => {
    if (!workspaceId) {
      setWorkspaceFiles([])
      return
    }
    setWorkspaceLoading(true)
    try {
      setWorkspaceFiles(await fetchWorkspaceFiles(workspaceId))
    } finally {
      setWorkspaceLoading(false)
    }
  }, [sessionId])

  const reloadSessions = useCallback(async () => {
    const seq = ++sessionListLoadSeq.current
    const res = await listSessions()
    if (seq !== sessionListLoadSeq.current) return
    setSessions(res.sessions)
  }, [setSessions])

  const upsertSession = useCallback(
    (session: SessionMeta) => {
      const currentSessions = useChatStore.getState().sessions
      setSessions([
        session,
        ...currentSessions.filter((item) => item.id !== session.id),
      ])
    },
    [setSessions],
  )

  useEffect(() => {
    reloadSessions().catch(() => {
      // Keep the chat usable even if the history endpoint is temporarily down.
    })
  }, [reloadSessions])

  useEffect(() => {
    refreshWorkspaceFiles().catch(() => undefined)
  }, [refreshWorkspaceFiles])

  const loadSessionIntoChat = useCallback(
    async (targetSessionId: string) => {
      const seq = ++messageLoadSeq.current
      messagesSessionId.current = null
      setSessionId(targetSessionId)
      loadSessionMessages([])
      const res = await loadSession(targetSessionId)
      if (seq !== messageLoadSeq.current) return
      if (useChatStore.getState().sessionId !== targetSessionId) return
      const msgs = res.messages
        .filter((m) => m.type === "user" || m.type === "assistant")
        .map((m) => ({
          role: (m.role === "user" || m.type === "user" ? "user" : "assistant") as "user" | "assistant",
          content: m.content,
          events: m.events ?? [],
          attachments: m.attachments ?? [],
          startTime: m.timestamp ? toMillis(m.timestamp) : undefined,
          endTime: m.type === "assistant" && m.timestamp ? toMillis(m.timestamp) : undefined,
        }))
      loadSessionMessages(msgs)
      messagesSessionId.current = targetSessionId
      upsertSession(res.session)
    },
    [loadSessionMessages, setSessionId, upsertSession],
  )

  const deleteConversation = useCallback(
    async (targetSessionId: string) => {
      await deleteSession(targetSessionId)
      const remainingSessions = useChatStore
        .getState()
        .sessions
        .filter((session) => session.id !== targetSessionId)
      setSessions(remainingSessions)
      if (targetSessionId === sessionId) {
        messagesSessionId.current = null
        if (remainingSessions.length > 0) {
          await loadSessionIntoChat(remainingSessions[0].id)
        } else {
          resetToNewChat()
        }
      }
    },
    [loadSessionIntoChat, resetToNewChat, sessionId, setSessions],
  )

  const createNewConversation = useCallback(async () => {
    if (creatingConversation.current) return
    const currentSessionId = useChatStore.getState().sessionId
    const currentMessages = useChatStore.getState().messages.filter((m) => m.role !== "system")
    if (currentSessionId && messagesSessionId.current === currentSessionId && currentMessages.length === 0) {
      return
    }
    creatingConversation.current = true
    abortStreaming()
    try {
      const { session_id, session } = await createSession()
      messageLoadSeq.current += 1
      messagesSessionId.current = session_id
      setSessionId(session_id)
      loadSessionMessages([])
      setWorkspaceFiles([])
      upsertSession(session)
    } finally {
      creatingConversation.current = false
    }
  }, [abortStreaming, loadSessionMessages, setSessionId, upsertSession])

  useEffect(() => {
    if (!sessionId) {
      messagesSessionId.current = null
      return
    }
    if (messagesSessionId.current === sessionId) return
    loadSessionIntoChat(sessionId)
      .catch(() => {
        messagesSessionId.current = null
        loadSessionMessages([])
      })
  }, [sessionId, loadSessionIntoChat, loadSessionMessages])

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
        events: msg.events,
        attachments: msg.attachments,
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
      } else if (part.type === "status") {
        events.push({ kind: "status", label: part.label, detail: part.detail })
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
      attachments: msg.attachments,
      createdAt,
      startedAt: msg.startTime,
      endedAt: msg.endTime,
    }
  }

  const paneMessages = messages
    .map(toPaneMessage)
    .filter((msg): msg is PaneChatMessage => msg !== null)

  const chatProjectFiles = useMemo(
    () =>
      workspaceFiles.map((file) => ({
        name: file.name,
        path: file.path,
        type: file.type === "dir" ? ("directory" as const) : ("file" as const),
        kind:
          file.kind === "html" || file.kind === "image" || file.kind === "code"
            ? file.kind
            : ("file" as const),
        size: file.size,
      })),
    [workspaceFiles],
  )
  const workspaceFileNames = useMemo(() => {
    const names = new Set<string>()
    for (const file of workspaceFiles) {
      names.add(file.name)
      names.add(file.name.split("/").filter(Boolean).at(-1) ?? file.name)
    }
    return names
  }, [workspaceFiles])

  function requestOpenWorkspaceFile(name: string) {
    const exact = workspaceFiles.find((file) => file.name === name)
    const byBase = workspaceFiles.find((file) => file.name.split("/").filter(Boolean).at(-1) === name)
    const target = exact ?? byBase
    if (!target) return
    setOpenRequest({ name: target.name, nonce: Date.now() })
  }

  const sendFromPane = async (
    prompt: string,
    paneAttachments: PaneChatAttachment[],
    _commentAttachments: ChatCommentAttachment[]
  ) => {
    if ((!prompt.trim() && paneAttachments.length === 0) || loading) return
    const question = prompt.trim()
    const contentParts: ContentPart[] = [
      ...paneAttachments.map((att) => ({
        ...(att.kind === "image"
          ? {
              type: "image_url" as const,
              image_url: { url: att.url ?? `/api/v1/files/raw?path=${encodeURIComponent(att.path)}` },
            }
          : {
              type: "file_url" as const,
              file_url: { url: att.path, file_name: att.name },
            }),
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

    addMessage({ role: "user", content: question, attachments: paneAttachments, startTime: Date.now() })
    setLoading(true)

    let currentSessionId = sessionId
    if (!currentSessionId) {
      try {
        const { session_id, session } = await createSession()
        currentSessionId = session_id
        messageLoadSeq.current += 1
        messagesSessionId.current = session_id
        setSessionId(session_id)
        upsertSession({
          ...session,
          title: question.slice(0, 50) + (question.length > 50 ? "..." : ""),
          updated_at: Date.now() / 1000,
          message_count: 1,
        })
      } catch {
        addMessage({ role: "system", content: "⚠️ 无法创建会话，对话不会被保存" })
        setLoading(false)
        return
      }
    } else {
      messagesSessionId.current = currentSessionId
    }

    const streamSessionId = currentSessionId
    const streamLoadSeq = messageLoadSeq.current

    sendChatStream({
      messages: requestMessages,
      model: requestModel,
      modelConfig: inlineModelConfig,
      session_id: currentSessionId,
      shouldApply: () =>
        Boolean(streamSessionId) &&
        messagesSessionId.current === streamSessionId &&
        messageLoadSeq.current === streamLoadSeq &&
        useChatStore.getState().sessionId === streamSessionId,
      onEvent: (event) => {
        const workspaceId = currentSessionId
        if (!workspaceId) return
        const artifact = artifactFromStreamEvent(event)
        const artifactKey = artifact ? `${workspaceId}:${artifact.key}` : ""
        if (!artifact || generatedArtifactKeys.current.has(artifactKey)) return
        generatedArtifactKeys.current.add(artifactKey)
        const write = writeWorkspaceTextFile(workspaceId, artifact.name, artifact.content, { overwrite: true })
          .then((file) => {
            if (file && artifact.shouldOpen) {
              setOpenRequest({ name: file.name, nonce: Date.now() })
            }
          })
          .catch(() => undefined)
        pendingArtifactWrites.current.push(write)
      },
      onDone: async () => {
        const writes = pendingArtifactWrites.current
        pendingArtifactWrites.current = []
        await Promise.allSettled(writes)
        await refreshWorkspaceFiles(currentSessionId)
        await reloadSessions()
      },
    })
  }

  const hasWorkspace = Boolean(sessionId && workspaceFiles.length > 0)

  return (
    <div className="h-full">
      <ResizableDivider
        initialLeftWidth={500}
        minLeftWidth={350}
        maxLeftWidth={750}
        showRightPanel={hasWorkspace}
        leftPanel={
          <ChatPane
            messages={paneMessages}
            streaming={loading}
            error={null}
            projectId={sessionId}
            projectFiles={chatProjectFiles}
            projectFileNames={workspaceFileNames}
            onRequestOpenFile={requestOpenWorkspaceFile}
            onEnsureProject={async () => {
              if (sessionId) return sessionId
              const { session_id, session } = await createSession()
              messageLoadSeq.current += 1
              messagesSessionId.current = session_id
              setSessionId(session_id)
              upsertSession(session)
              await refreshWorkspaceFiles(session_id)
              return session_id
            }}
            onSend={sendFromPane}
            onStop={abortStreaming}
            conversations={sessions.map((session) => ({
              id: session.id,
              title: session.title,
              createdAt: toMillis(session.created_at),
              updatedAt: toMillis(session.updated_at),
            }))}
            activeConversationId={sessionId ?? "current"}
            onSelectConversation={(id) => {
              if (id !== sessionId || messagesSessionId.current !== id) {
                abortStreaming()
                loadSessionIntoChat(id).catch(() => undefined)
              }
            }}
            onDeleteConversation={(id) => {
              deleteConversation(id).catch(() => undefined)
            }}
            onNewConversation={() => {
              createNewConversation().catch(() => {
                addMessage({ role: "system", content: "⚠️ 无法创建新会话，请稍后再试" })
              })
            }}
          />
        }
        rightPanel={
          sessionId ? (
            <FileWorkspace
              workspaceId={sessionId}
              files={workspaceFiles}
              loading={workspaceLoading}
              onRefreshFiles={() => refreshWorkspaceFiles(sessionId)}
              openRequest={openRequest}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
              Start or select a conversation to open its file workspace.
            </div>
          )
        }
      />
    </div>
  )
}

function toMillis(timestamp: number): number {
  return timestamp < 10_000_000_000 ? timestamp * 1000 : timestamp
}
