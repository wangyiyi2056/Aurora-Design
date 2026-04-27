import { useState, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { X } from "lucide-react"
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
import { useChatStream } from "@/features/chat/hooks/use-chat-stream"
import { ChatMessageList } from "@/features/chat/components/chat-message-list"
import { ChatInput } from "@/features/chat/components/chat-input"
import { ConversationList } from "@/features/chat/components/conversation-list"
import { MobileNav } from "@/features/mobile/components/mobile-nav"
import { useChatTools } from "@/features/chat/hooks/use-chat-tools"
import { listSkills } from "@/services/models"
import { listKnowledge, queryKnowledge } from "@/services/knowledge"
import { listDatasources } from "@/services/database"
import { createSession, loadSession } from "@/services/chat"
import type { ChatMessage, ContentPart } from "@/services/chat"

export default function MobileChatPage() {
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
    setSessionId,
    loadSessionMessages,
    resetToNewChat,
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
  const [historyOpen, setHistoryOpen] = useState(false)

  const [selectedSkill, setSelectedSkill] = useState<string>()
  const [selectedKnowledge, setSelectedKnowledge] = useState<string>()
  const [selectedDatabase, setSelectedDatabase] = useState<string>()

  const skillsQuery = useQuery({
    queryKey: ["skills"],
    queryFn: listSkills,
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

  const chatStream = useChatStream({
    onSuccess: (content) => {
      addMessage({ role: "assistant", content })
      setLoading(false)
      clearAttachments()
    },
    onError: (error) => {
      addMessage({ role: "assistant", content: "Error: " + error.message })
      setLoading(false)
    },
  })

  // Restore session on mount
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
        .catch(() => {})
    }
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const modelConfig = models.find((m) => m.name === model)

  const send = async () => {
    if (!input.trim() || loading) return

    const contentParts: ContentPart[] = []

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
        const msg = err instanceof Error ? err.message : "知识库查询失败"
        addMessage({ role: "assistant", content: `❌ 知识库查询失败：${msg}` })
        toast.error(t("chat.knowledgeQueryFailed") || "知识库查询失败")
        setLoading(false)
        return
      }
    }

    contentParts.push({ type: "text", text: input.trim() })

    const existingSystem =
      messages.find((m) => m.role === "system")?.content || ""

    const newMessages: ChatMessage[] = [
      { role: "system", content: existingSystem },
      ...messages.filter((m) => m.role !== "system"),
      { role: "user", content: contentParts },
    ]

    const extInfo: Record<string, unknown> = {}
    let selectParam: string | undefined

    const skillAtt = attachments.find((a) => a.type === "skill")
    if (skillAtt) {
      selectParam = skillAtt.name
      extInfo.skill_name = skillAtt.name
    }

    const dbAtt = attachments.find((a) => a.type === "database")
    if (dbAtt) {
      extInfo.database_name = dbAtt.name
    }

    // Create session if needed
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

    addMessage({ role: "user", content: input.trim() })
    setInput("")
    setLoading(true)
    chatStream.mutate({
      messages: newMessages,
      model,
      modelConfig: modelConfig
        ? {
            model_name: modelConfig.name,
            base_url: modelConfig.baseUrl,
            api_key: modelConfig.apiKey,
          }
        : { model_name: model, base_url: "", api_key: "" },
      selectParam,
      extInfo,
      session_id: currentSessionId,
    })
  }

  const hasConversation = messages.filter((m) => m.role !== "system").length > 0

  return (
    <div className="flex h-screen flex-col bg-background">
      <MobileNav
        showNewChat
        onNewChat={resetToNewChat}
        showHistory
        onHistory={() => setHistoryOpen(true)}
      />
      <div className="flex-1 overflow-hidden">
        {hasConversation ? (
          <ChatMessageList messages={messages} loading={loading} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center text-muted-foreground">
            <div className="text-lg font-medium text-foreground mb-2">ChatBI</div>
            <p>Start a new conversation</p>
          </div>
        )}
      </div>
      <div className="border-t border-border bg-card p-3">
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
          onModelChange={(m) => useChatStore.getState().setModel(m)}
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
      </div>

      {/* History Drawer */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 bg-black/50" onClick={() => setHistoryOpen(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[70vh] bg-surface rounded-t-2xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-border">
              <span className="font-semibold text-sm">Conversations</span>
              <button
                type="button"
                onClick={() => setHistoryOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-2">
              <ConversationList
                activeId={sessionId}
                collapsed={false}
                onSelect={() => setHistoryOpen(false)}
                onNewChat={() => {
                  resetToNewChat()
                  setHistoryOpen(false)
                }}
              />
            </div>
          </div>
        </div>
      )}

      <Dialog open={skillModalOpen} onOpenChange={setSkillModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("chat.useSkill")}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Select value={selectedSkill} onValueChange={setSelectedSkill}>
              <SelectTrigger>
                <SelectValue placeholder={t("chat.selectSkill")} />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(skillsQuery.data || {}).map(([key, val]) => (
                  <SelectItem key={key} value={key}>
                    {key} ({String(val)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSkillModalOpen(false)}>
              {t("actions.cancel", { ns: "common" })}
            </Button>
            <Button onClick={() => {
              if (selectedSkill) {
                setSkill(selectedSkill)
                setSkillModalOpen(false)
              }
            }}>
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
            <Button onClick={() => {
              if (selectedKnowledge) {
                setKnowledge(selectedKnowledge)
                setKnowledgeModalOpen(false)
              }
            }}>
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
            <Button onClick={() => {
              if (selectedDatabase) {
                setDatabase(selectedDatabase)
                setDatabaseModalOpen(false)
              }
            }}>
              {t("actions.add", { ns: "common" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
