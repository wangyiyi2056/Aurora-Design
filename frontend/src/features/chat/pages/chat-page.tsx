import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { Modal, Select, message } from "antd"
import { useChatStore } from "@/stores/chat-store"
import { useModelsStore } from "@/stores/models-store"
import { useChatStream } from "@/features/chat/hooks/use-chat-stream"
import { ChatHeader } from "@/features/chat/components/chat-header"
import { ChatMessageList } from "@/features/chat/components/chat-message-list"
import { ChatInput } from "@/features/chat/components/chat-input"
import { ChatWelcome } from "@/features/chat/components/chat-welcome"
import { useChatTools } from "@/features/chat/hooks/use-chat-tools"
import { listSkills } from "@/services/models"
import { listKnowledge, queryKnowledge } from "@/services/knowledge"
import { listDatasources } from "@/services/database"
import type { ChatMessage, ContentPart } from "@/services/chat"

export default function ChatPage() {
  const { t } = useTranslation(["chat", "common"])
  const {
    messages,
    input,
    loading,
    model,
    setInput,
    addMessage,
    setLoading,
    setModel,
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
        message.error(t("chat.knowledgeQueryFailed") || "知识库查询失败")
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
    })
  }

  const hasConversation =
    messages.filter((m) => m.role !== "system").length > 0

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-48px)]">
      <ChatHeader model={model} onModelChange={setModel} />
      {hasConversation ? (
        <ChatMessageList messages={messages} loading={loading} />
      ) : (
        <div className="flex-1">
          <ChatWelcome
            onSelect={(prompt) => {
              setInput(prompt)
              setTimeout(() => {
                const userMsg = { role: "user" as const, content: prompt }
                addMessage(userMsg)
                setInput("")
                setLoading(true)
                chatStream.mutate({
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
                      }
                    : { model_name: model, base_url: "", api_key: "" },
                })
              }, 300)
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
      />
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFileSelect(file)
          if (e.target) e.target.value = ""
        }}
      />

      <Modal
        title={t("chat.useSkill")}
        open={skillModalOpen}
        onCancel={() => setSkillModalOpen(false)}
        onOk={() => {
          if (selectedSkill) {
            setSkill(selectedSkill)
            setSkillModalOpen(false)
          }
        }}
        okText={t("actions.add", { ns: "common" })}
        cancelText={t("actions.cancel", { ns: "common" })}
      >
        <Select
          className="w-full mt-4"
          placeholder={t("chat.selectSkill")}
          value={selectedSkill}
          onChange={setSelectedSkill}
          options={Object.entries(skillsQuery.data || {}).map(([key, val]) => ({
            value: key,
            label: `${key} (${val})`,
          }))}
        />
      </Modal>

      <Modal
        title={t("chat.useKnowledge")}
        open={knowledgeModalOpen}
        onCancel={() => setKnowledgeModalOpen(false)}
        onOk={() => {
          if (selectedKnowledge) {
            setKnowledge(selectedKnowledge)
            setKnowledgeModalOpen(false)
          }
        }}
        okText={t("actions.add", { ns: "common" })}
        cancelText={t("actions.cancel", { ns: "common" })}
      >
        <Select
          className="w-full mt-4"
          placeholder={t("chat.selectKnowledge")}
          value={selectedKnowledge}
          onChange={setSelectedKnowledge}
          options={(knowledgeQuery.data || []).map((name) => ({
            value: name,
            label: name,
          }))}
        />
      </Modal>

      <Modal
        title={t("chat.useDatabase")}
        open={databaseModalOpen}
        onCancel={() => setDatabaseModalOpen(false)}
        onOk={() => {
          if (selectedDatabase) {
            setDatabase(selectedDatabase)
            setDatabaseModalOpen(false)
          }
        }}
        okText={t("actions.add", { ns: "common" })}
        cancelText={t("actions.cancel", { ns: "common" })}
      >
        <Select
          className="w-full mt-4"
          placeholder={t("chat.selectDatabase")}
          value={selectedDatabase}
          onChange={setSelectedDatabase}
          options={(datasourcesQuery.data || []).map((ds) => ({
            value: ds.name,
            label: `${ds.name} (${ds.db_type})`,
          }))}
        />
      </Modal>
    </div>
  )
}
