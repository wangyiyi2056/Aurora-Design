import { useState, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { useChatStore } from "@/stores/chat-store"
import { useModelsStore } from "@/stores/models-store"
import { sendChatStream } from "@/features/chat/hooks/use-chat-stream"
import { ChatMessageList } from "@/features/chat/components/chat-message-list"
import { ChatInput } from "@/features/chat/components/chat-input"
import { ChatWelcome } from "@/features/chat/components/chat-welcome"
import { useChatTools } from "@/features/chat/hooks/use-chat-tools"
import { listSkillsDetail, type SkillInfo } from "@/services/models"
import { listKnowledge, queryKnowledge } from "@/services/knowledge"
import { listDatasources } from "@/services/database"
import { createSession, loadSession } from "@/services/chat"
import type { ChatMessage, ContentPart } from "@/services/chat"

export default function ChatPage() {
  const { t } = useTranslation(["chat", "common"])
  const {
    messages,
    input,
    loading,
    model,
    sessionId,
    setInput,
    addMessage,
    setLoading,
    setModel,
    setSessionId,
    loadSessionMessages,
  } = useChatStore()
  const { models } = useModelsStore()

  const {
    attachments,
    fileInputRef,
    attachFile,
    handleFileSelect,
    setSkill,
    setKnowledge,
    setDatabase,
    removeAttachment,
    clearAttachments,
  } = useChatTools()

  const [skillModalOpen, setSkillModalOpen] = useState(false)
  const [knowledgeModalOpen, setKnowledgeModalOpen] = useState(false)
  const [databaseModalOpen, setDatabaseModalOpen] = useState(false)

  const [selectedSkill, setSelectedSkill] = useState<string>()
  const [selectedKnowledge, setSelectedKnowledge] = useState<string>()
  const [selectedDatabase, setSelectedDatabase] = useState<string>()

  const skillsQuery = useQuery({
    queryKey: ["skills"],
    queryFn: listSkillsDetail,
    enabled: skillModalOpen,
  })

  const knowledgeQuery = useQuery({
    queryKey: ["knowledge"],
    queryFn: listKnowledge,
    enabled: knowledgeModalOpen,
  })

  const datasourcesQuery = useQuery({
    queryKey: ["datasources"],
    queryFn: async () => {
      const res = await listDatasources()
      return res.items
    },
    enabled: databaseModalOpen,
  })

  const modelConfig = models.find((m) => m.name === model)

  const send = async () => {
    if (!input.trim() || loading) return

    const contentParts: ContentPart[] = []

    // File attachments
    const fileAttachments = attachments.filter((a) => a.type === "file")
    for (const att of fileAttachments) {
      if (att.content?.startsWith("data:image/")) {
        contentParts.push({
          type: "image_url",
          image_url: { url: att.content },
        })
      } else if (att.content) {
        contentParts.push({
          type: "file_url",
          file_url: { url: att.content, file_name: att.name },
        })
      }
    }

    // Knowledge base retrieval
    const knowledgeAtt = attachments.find((a) => a.type === "knowledge")
    if (knowledgeAtt) {
      setLoading(true)
      try {
        const ctx = await queryKnowledge(knowledgeAtt.name, input.trim())
        const results = Array.isArray(ctx.results)
          ? ctx.results.map((r: { content: string }) => r.content).join("\n---\n")
          : JSON.stringify(ctx)
        contentParts.push({
          type: "text",
          text: `以下是来自知识库 "${knowledgeAtt.name}" 的检索结果：\n${results}`,
        })
      } catch (err) {
        toast.error(t("chat.knowledgeQueryFailed") || "知识库查询失败")
        setLoading(false)
        return
      }
    }

    // User text
    contentParts.push({ type: "text", text: input.trim() })

    const existingSystem =
      messages.find((m) => m.role === "system")?.content || ""

    const newMessages: ChatMessage[] = [
      { role: "system", content: existingSystem },
      ...messages.filter((m) => m.role !== "system"),
      { role: "user", content: contentParts },
    ]

    // Build extInfo and selectParam
    const extInfo: Record<string, unknown> = {}
    let selectParam: string | undefined

    // Detect client type: Electron desktop app or web browser
    extInfo.client_type =
      typeof window !== "undefined" && "electronAPI" in window
        ? "desktop"
        : "web"

    const skillAtt = attachments.find((a) => a.type === "skill")
    if (skillAtt) {
      selectParam = skillAtt.name
      extInfo.skill_name = skillAtt.name
    }

    const dbAtt = attachments.find((a) => a.type === "database")
    if (dbAtt) {
      extInfo.database_name = dbAtt.name
    }

    addMessage({ role: "user", content: input.trim() })
    setInput("")
    setLoading(true)
    clearAttachments()

    // Create a new session if we don't have one yet
    let currentSessionId = sessionId
    if (!currentSessionId) {
      try {
        const { session_id } = await createSession()
        currentSessionId = session_id
        setSessionId(session_id)
      } catch {
        // Continue without session persistence
      }
    }

    sendChatStream({
      messages: newMessages,
      model,
      modelConfig: modelConfig
        ? {
            model_name: modelConfig.name,
            base_url: modelConfig.baseUrl,
            api_key: modelConfig.apiKey,
            model_type: modelConfig.type,
          }
        : { model_name: model, base_url: "", api_key: "", model_type: "llm" },
      selectParam,
      extInfo,
      session_id: currentSessionId,
    })
  }

  // Restore session messages on mount if we have a sessionId but no messages
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
          // Session not found or error — start fresh
        })
    }
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasConversation =
    messages.filter((m) => m.role !== "system").length > 0

  const handleSkillConfirm = () => {
    if (selectedSkill) {
      setSkill(selectedSkill)
      setSkillModalOpen(false)
    }
  }

  const handleKnowledgeConfirm = () => {
    if (selectedKnowledge) {
      setKnowledge(selectedKnowledge)
      setKnowledgeModalOpen(false)
    }
  }

  const handleDatabaseConfirm = () => {
    if (selectedDatabase) {
      setDatabase(selectedDatabase)
      setDatabaseModalOpen(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-48px)]">
      {hasConversation ? (
        <ChatMessageList messages={messages} loading={loading} />
      ) : (
        <div className="flex-1">
          <ChatWelcome
            onSelect={async (prompt) => {
              setInput(prompt)
              setTimeout(async () => {
                const userMsg = { role: "user" as const, content: prompt }
                addMessage(userMsg)
                setInput("")
                setLoading(true)

                // Create session for the new chat
                let currentSessionId = sessionId
                if (!currentSessionId) {
                  try {
                    const { session_id } = await createSession()
                    currentSessionId = session_id
                    setSessionId(session_id)
                  } catch {
                    // Continue without session
                  }
                }

                sendChatStream({
                  messages: [
                    { role: "system" as const, content: messages.find((m) => m.role === "system")?.content || "" },
                    userMsg,
                  ],
                  model,
                  modelConfig: modelConfig
                    ? {
                        model_name: modelConfig.name,
                        base_url: modelConfig.baseUrl,
                        api_key: modelConfig.apiKey,
                        model_type: modelConfig.type,
                      }
                    : { model_name: model, base_url: "", api_key: "", model_type: "llm" },
                  extInfo: {
                    client_type:
                      typeof window !== "undefined" && "electronAPI" in window
                        ? "desktop"
                        : "web",
                  },
                  session_id: currentSessionId,
                })
              }, 0)
            }}
          />
        </div>
      )}
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={send}
        loading={loading}
        attachments={attachments}
        onRemoveAttachment={removeAttachment}
        onAttachFile={attachFile}
        onUseSkill={() => setSkillModalOpen(true)}
        onUseKnowledge={() => setKnowledgeModalOpen(true)}
        onUseDatabase={() => setDatabaseModalOpen(true)}
        model={model}
        onModelChange={setModel}
      />
      <input
        type="file"
        ref={fileInputRef}
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: -1,
          overflow: "hidden",
          clip: "rect(0, 0, 0, 0)",
          whiteSpace: "nowrap",
          borderWidth: 0,
        }}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFileSelect(file)
          if (e.target) e.target.value = ""
        }}
      />

      <Dialog open={skillModalOpen} onOpenChange={setSkillModalOpen}>
        <DialogContent className="max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{t("chat.useSkill")}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[400px] overflow-y-auto py-4">
            {(skillsQuery.data?.skills || []).map((skill: SkillInfo) => (
              <div
                key={skill.name}
                className={`p-3 rounded-lg mb-2 cursor-pointer border ${
                  selectedSkill === skill.name
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                }`}
                onClick={() => setSelectedSkill(skill.name)}
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{skill.name}</span>
                  {skill.is_builtin && (
                    <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                      内置
                    </span>
                  )}
                </div>
                <div className="text-foreground text-sm mt-1">
                  {skill.description_cn || skill.description}
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSkillModalOpen(false)}>
              {t("actions.cancel", { ns: "common" })}
            </Button>
            <Button onClick={handleSkillConfirm}>
              {t("actions.add", { ns: "common" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={knowledgeModalOpen} onOpenChange={setKnowledgeModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("chat.useKnowledge")}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Select value={selectedKnowledge} onValueChange={setSelectedKnowledge}>
              <SelectTrigger>
                <SelectValue placeholder={t("chat.selectKnowledge")} />
              </SelectTrigger>
              <SelectContent>
                {(knowledgeQuery.data || []).map((name) => (
                  <SelectItem key={name} value={name}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setKnowledgeModalOpen(false)}>
              {t("actions.cancel", { ns: "common" })}
            </Button>
            <Button onClick={handleKnowledgeConfirm}>
              {t("actions.add", { ns: "common" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={databaseModalOpen} onOpenChange={setDatabaseModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("chat.useDatabase")}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Select value={selectedDatabase} onValueChange={setSelectedDatabase}>
              <SelectTrigger>
                <SelectValue placeholder={t("chat.selectDatabase")} />
              </SelectTrigger>
              <SelectContent>
                {(datasourcesQuery.data || []).map((ds) => (
                  <SelectItem key={ds.name} value={ds.name}>
                    {ds.name} ({ds.db_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDatabaseModalOpen(false)}>
              {t("actions.cancel", { ns: "common" })}
            </Button>
            <Button onClick={handleDatabaseConfirm}>
              {t("actions.add", { ns: "common" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}