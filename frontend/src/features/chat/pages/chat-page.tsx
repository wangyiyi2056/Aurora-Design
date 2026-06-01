import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ChatPane } from "@/features/chat/components/chat-pane"
import { FileWorkspace } from "@/features/file-workspace/components/file-workspace"
import { ResizableDivider } from "@/components/ui/resizable-divider"
import {
  artifactFromToolCallStartEvent,
  artifactFromStreamEvent,
  artifactsFromAgentEvents,
  artifactsFromAssistantText,
  artifactsFromPartialAssistantText,
  canonicalArtifactsForAssistant,
  type GeneratedWorkspaceArtifact,
} from "@/features/file-workspace/runtime/generated-artifacts"
import { fetchWorkspaceFiles, writeWorkspaceTextFile } from "@/features/file-workspace/services/workspace-files"
import type { WorkspaceFile } from "@/features/file-workspace/types"
import { sendChatStream } from "@/features/chat/hooks/use-chat-stream"
import {
  createMessageId,
  eventsFromMessage,
  resolvedMessageText,
  textFromEvents,
  textFromMessageContent,
} from "@/features/chat/runtime/message-persistence"
import { mergeSessionList } from "@/features/chat/runtime/session-list"
import type {
  AgentEvent,
  ChatAttachment as PaneChatAttachment,
  ChatCommentAttachment,
  ChatMessage as PaneChatMessage,
} from "@/features/chat/types"
import { createSession, deleteSession, listSessions, loadSession, upsertSessionMessage } from "@/services/chat"
import type { APIChatMessage, ContentPart } from "@/services/chat"
import { listDesignSkills, type DesignSkillSummary } from "@/services/design-skills"
import { listDesignSystems, type DesignSystemSummary } from "@/services/design-systems"
import { listCustomPrompts, type PromptTemplate } from "@/services/prompts"
import { useDatasources } from "@/features/construct/database/hooks/use-datasources"
import { useProviderStore } from "@/stores/provider-store"
import { useChatStore, type SessionMeta } from "@/stores/chat-store"
import { agentDisplayName } from "@/features/chat/utils/agent-labels"

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
  const modelDisplayName = buildCurrentModelDisplayName({
    providerMode,
    protocol: byok.protocol,
    apiModel: byok.model || model,
    agentId: activeAgentId || model,
  })
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [workspaceVisible, setWorkspaceVisible] = useState(false)
  const [openRequest, setOpenRequest] = useState<{ name: string; nonce: number } | null>(null)
  const [designSkills, setDesignSkills] = useState<DesignSkillSummary[]>([])
  const [designSkillsLoading, setDesignSkillsLoading] = useState(false)
  const [designSkillsError, setDesignSkillsError] = useState<string | null>(null)
  const [selectedDesignSkillId, setSelectedDesignSkillId] = useState<string | null>(null)
  const [designSystems, setDesignSystems] = useState<DesignSystemSummary[]>([])
  const [designSystemsLoading, setDesignSystemsLoading] = useState(false)
  const [designSystemsError, setDesignSystemsError] = useState<string | null>(null)
  const [selectedDesignSystemId, setSelectedDesignSystemId] = useState<string | null>(null)
  const [selectedDatasourceName, setSelectedDatasourceName] = useState<string | null>(null)
  const { data: dsData, isLoading: dsLoading } = useDatasources()
  const [customPrompts, setCustomPrompts] = useState<PromptTemplate[]>([])
  const generatedArtifactKeys = useRef<Set<string>>(new Set())
  const messageLoadSeq = useRef(0)
  const sessionListLoadSeq = useRef(0)
  const messagesSessionId = useRef<string | null>(null)
  const creatingConversation = useRef(false)

  useEffect(() => {
    let cancelled = false
    setDesignSkillsLoading(true)
    setDesignSkillsError(null)
    listDesignSkills()
      .then((skills) => {
        if (!cancelled) setDesignSkills(skills)
      })
      .catch((error) => {
        if (!cancelled) {
          setDesignSkills([])
          setDesignSkillsError(error instanceof Error ? error.message : "Design skills unavailable")
        }
      })
      .finally(() => {
        if (!cancelled) setDesignSkillsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setDesignSystemsLoading(true)
    setDesignSystemsError(null)
    listDesignSystems()
      .then((systems) => {
        if (!cancelled) setDesignSystems(systems)
      })
      .catch((error) => {
        if (!cancelled) {
          setDesignSystems([])
          setDesignSystemsError(error instanceof Error ? error.message : "Design systems unavailable")
        }
      })
      .finally(() => {
        if (!cancelled) setDesignSystemsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    listCustomPrompts()
      .then((res) => {
        if (!cancelled) setCustomPrompts(res.items)
      })
      .catch(() => {
        if (!cancelled) setCustomPrompts([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const refreshWorkspaceFiles = useCallback(async (workspaceId = sessionId) => {
    if (!workspaceId) {
      setWorkspaceFiles([])
      setWorkspaceVisible(false)
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
      setSessions(mergeSessionList(currentSessions, session))
    },
    [setSessions],
  )

  const upsertWorkspaceFile = useCallback((file: WorkspaceFile) => {
    setWorkspaceFiles((current) => [
      file,
      ...current.filter((item) => item.name !== file.name),
    ])
  }, [])

  const persistWorkspaceArtifacts = useCallback(
    async (
      workspaceId: string,
      artifacts: GeneratedWorkspaceArtifact[],
      options: { openHtml?: boolean } = {},
    ) => {
      const writes: Promise<WorkspaceFile | null>[] = []
      for (const artifact of artifacts) {
        const artifactKey = `${workspaceId}:${artifact.key}`
        if (generatedArtifactKeys.current.has(artifactKey)) continue
        generatedArtifactKeys.current.add(artifactKey)
        const write = writeWorkspaceTextFile(workspaceId, artifact.name, artifact.content, {
          overwrite: true,
          encoding: artifact.encoding,
        })
          .then((file) => {
            if (file) {
              upsertWorkspaceFile(file)
              setWorkspaceVisible(true)
              if (artifact.shouldOpen && options.openHtml) {
                setOpenRequest({ name: file.name, nonce: Date.now() })
              }
            }
            return file
          })
          .catch(() => null)
        writes.push(write)
      }
      const results = await Promise.allSettled(writes)
      return results.filter((result) => result.status === "fulfilled" && result.value).length
    },
    [upsertWorkspaceFile],
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
      setWorkspaceVisible(false)
      const res = await loadSession(targetSessionId)
      if (seq !== messageLoadSeq.current) return
      if (useChatStore.getState().sessionId !== targetSessionId) return
      const msgs = res.messages
        .filter((m) => m.type === "user" || m.type === "assistant")
        .map((m) => {
          const content = m.content || textFromEvents(m.events)
          return {
            id: m.id,
            role: (m.role === "user" || m.type === "user" ? "user" : "assistant") as "user" | "assistant",
            content,
            events: m.events ?? [],
            attachments: m.attachments ?? [],
            startTime: m.timestamp ? toMillis(m.timestamp) : undefined,
            endTime: m.type === "assistant" && m.end_time ? toMillis(m.end_time) : undefined,
          }
        })
      loadSessionMessages(msgs)
      messagesSessionId.current = targetSessionId
      upsertSession(res.session)
      const canonicalArtifacts = msgs
        .filter((message) => message.role === "assistant")
        .flatMap((message) =>
          canonicalArtifactsForAssistant(
            artifactsFromAssistantText(resolvedMessageText(message)),
            artifactsFromAgentEvents(message.events),
          ),
        )
      const artifactCount = await persistWorkspaceArtifacts(
        targetSessionId,
        canonicalArtifacts,
        { openHtml: true },
      )
      if (artifactCount > 0 && messagesSessionId.current === targetSessionId) {
        await refreshWorkspaceFiles(targetSessionId)
      }
    },
    [loadSessionMessages, persistWorkspaceArtifacts, refreshWorkspaceFiles, setSessionId, upsertSession],
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
      setWorkspaceVisible(false)
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
        id: msg.id ?? `${msg.role}-${index}-${createdAt}`,
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
    if (msg.events) {
      const nonContentEvents = msg.events.filter(
        (e) => e.kind !== "text" && e.kind !== "thinking" && e.kind !== "status" && e.kind !== "tool_use" && e.kind !== "tool_result"
      )
      events.push(...nonContentEvents)
    }
    return {
      id: msg.id ?? `${msg.role}-${index}-${createdAt}`,
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
    _commentAttachments: ChatCommentAttachment[],
    customPromptIds: string[] = [],
  ) => {
    if ((!prompt.trim() && paneAttachments.length === 0 && customPromptIds.length === 0) || loading) return
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
              file_url: { url: att.url ?? att.path, file_name: att.name },
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

    const userMessageId = createMessageId("user")
    const assistantMessageId = createMessageId("assistant")
    const userTimestamp = Date.now()
    addMessage({ id: userMessageId, role: "user", content: question, attachments: paneAttachments, startTime: userTimestamp })
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
    const streamArtifactWrites: Promise<unknown>[] = []
    let canonicalHtmlName: string | null = null
    const normalizeTurnArtifacts = (artifacts: GeneratedWorkspaceArtifact[]) =>
      artifacts.map((artifact) => {
        if (!isHtmlWorkspaceArtifact(artifact)) return artifact
        if (!canonicalHtmlName) canonicalHtmlName = artifact.name
        return { ...artifact, name: canonicalHtmlName }
      })
    const saveSessionMessage = async (
      messageId: string,
      payload: Parameters<typeof upsertSessionMessage>[2],
    ) => {
      const res = await upsertSessionMessage(streamSessionId, messageId, payload)
      upsertSession(res.session)
      return res
    }
    try {
      await saveSessionMessage(userMessageId, {
        type: "user",
        role: "user",
        content: question,
        attachments: paneAttachments,
        timestamp: userTimestamp / 1000,
      })
      await saveSessionMessage(assistantMessageId, {
        type: "assistant",
        role: "assistant",
        content: "",
        events: [],
        timestamp: Date.now() / 1000,
      })
      await reloadSessions()
    } catch {
      addMessage({ role: "system", content: "⚠️ 当前消息暂时无法保存，生成会继续进行" })
    }
    setWorkspaceVisible(true)

    sendChatStream({
      messages: requestMessages,
      model: requestModel,
      modelConfig: inlineModelConfig,
      session_id: currentSessionId,
      assistantMessageId,
      extInfo: {
        frontend_persistence: true,
        user_message_id: userMessageId,
        assistant_message_id: assistantMessageId,
        ...(customPromptIds.length > 0 ? { custom_prompt_ids: customPromptIds } : {}),
        ...(selectedDesignSkillId ? { design_skill_id: selectedDesignSkillId } : {}),
        ...(selectedDesignSystemId ? { design_system_id: selectedDesignSystemId } : {}),
        ...(selectedDatasourceName ? { database_name: selectedDatasourceName } : {}),
      },
      shouldApply: () =>
        Boolean(streamSessionId) &&
        messagesSessionId.current === streamSessionId &&
        messageLoadSeq.current === streamLoadSeq &&
        useChatStore.getState().sessionId === streamSessionId,
      onEvent: (event) => {
        const workspaceId = streamSessionId
        if (!workspaceId) return
        const artifact = normalizeTurnArtifacts(
          [artifactFromToolCallStartEvent(event) ?? artifactFromStreamEvent(event)]
            .filter((item): item is GeneratedWorkspaceArtifact => item !== null),
        )[0]
        const artifactKey = artifact ? `${workspaceId}:${artifact.key}` : ""
        if (!artifact || generatedArtifactKeys.current.has(artifactKey)) return
        generatedArtifactKeys.current.add(artifactKey)
        const write = writeWorkspaceTextFile(workspaceId, artifact.name, artifact.content, { overwrite: true })
          .then((file) => {
            if (file) {
              upsertWorkspaceFile(file)
              setWorkspaceVisible(true)
              if (artifact.shouldOpen) {
                setOpenRequest({ name: file.name, nonce: Date.now() })
              }
            }
          })
          .catch(() => undefined)
        streamArtifactWrites.push(write)
      },
      onMessageUpdate: async (message) => {
        const partialArtifacts = normalizeTurnArtifacts(
          artifactsFromPartialAssistantText(resolvedMessageText(message)),
        )
        if (partialArtifacts.length > 0) {
          streamArtifactWrites.push(
            persistWorkspaceArtifacts(streamSessionId, partialArtifacts, {
              openHtml: messagesSessionId.current === streamSessionId,
            }),
          )
        }
        await saveSessionMessage(assistantMessageId, {
          type: "assistant",
          role: "assistant",
          content: textFromMessageContent(message.content),
          events: eventsFromMessage(message),
          timestamp: (message.startTime ?? Date.now()) / 1000,
          end_time: message.endTime ? message.endTime / 1000 : undefined,
        })
      },
      onFinalMessage: async (message) => {
        const text = resolvedMessageText(message)
        try {
          await saveSessionMessage(assistantMessageId, {
            type: "assistant",
            role: "assistant",
            content: text,
            events: eventsFromMessage(message),
            timestamp: (message.startTime ?? Date.now()) / 1000,
            end_time: (message.endTime ?? Date.now()) / 1000,
          })
          await persistWorkspaceArtifacts(
            streamSessionId,
            normalizeTurnArtifacts(
              canonicalArtifactsForAssistant(
                artifactsFromAssistantText(text),
                artifactsFromAgentEvents(eventsFromMessage(message)),
              ),
            ),
            { openHtml: messagesSessionId.current === streamSessionId },
          )
          await Promise.allSettled(streamArtifactWrites)
          if (messagesSessionId.current === streamSessionId) {
            await refreshWorkspaceFiles(streamSessionId)
          }
        } finally {
          await reloadSessions().catch(() => undefined)
        }
      },
      onDone: async () => {
        if (messagesSessionId.current === streamSessionId) {
          await refreshWorkspaceFiles(streamSessionId)
        }
      },
    })
  }

  const hasWorkspace = Boolean(sessionId && (workspaceVisible || workspaceFiles.length > 0))

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
            modelDisplayName={modelDisplayName}
            designSkills={designSkills}
            designSkillsLoading={designSkillsLoading}
            designSkillsError={designSkillsError}
            selectedDesignSkillId={selectedDesignSkillId}
            onSelectDesignSkill={setSelectedDesignSkillId}
            designSystems={designSystems}
            designSystemsLoading={designSystemsLoading}
            designSystemsError={designSystemsError}
            selectedDesignSystemId={selectedDesignSystemId}
            onSelectDesignSystem={setSelectedDesignSystemId}
            customPrompts={customPrompts}
            datasources={dsData?.items ?? []}
            datasourcesLoading={dsLoading}
            selectedDatasourceName={selectedDatasourceName}
            onSelectDatasource={setSelectedDatasourceName}
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

function isHtmlWorkspaceArtifact(artifact: GeneratedWorkspaceArtifact): boolean {
  return artifact.name.toLowerCase().endsWith(".html")
}

function buildCurrentModelDisplayName({
  providerMode,
  protocol,
  apiModel,
  agentId,
}: {
  providerMode: string
  protocol: string
  apiModel: string
  agentId: string
}): string {
  if (providerMode === "api") {
    return `${apiProviderLabel(protocol)}-${apiModel || "default"}`
  }
  if (providerMode === "embedding") {
    return `CLI-${cliAgentLabel(agentId)}`
  }
  return `CLI-${cliAgentLabel(agentId)}`
}

function apiProviderLabel(protocol: string): string {
  if (protocol === "openai") return "OpenAI"
  if (protocol === "anthropic") return "Anthropic"
  if (protocol === "azure") return "Azure"
  if (protocol === "google") return "Google"
  return protocol || "API"
}

function cliAgentLabel(agentId: string): string {
  if (agentId === "claude") return "Claude Code"
  if (agentId === "codex") return "Codex"
  return agentDisplayName(agentId) ?? (agentId || "CLI")
}
