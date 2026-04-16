import { useParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { ChatMessageItem } from "@/features/chat/components/chat-message-item"

const mockMessages = [
  { role: "user" as const, content: "Hello, what can you do?" },
  { role: "assistant" as const, content: "I can help with data analysis, SQL generation, and knowledge base queries." },
]

export default function SharePage() {
  const { id } = useParams()
  const { t } = useTranslation("chat")

  return (
    <div className="max-w-3xl mx-auto h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold m-0">{t("share.title")}</h2>
        <span className="text-xs text-text-secondary">ID: {id}</span>
      </div>
      <div className="flex-1 overflow-y-auto flex flex-col gap-4 pb-4 px-2">
        {mockMessages.map((m, i) => (
          <ChatMessageItem key={i} role={m.role} content={m.content} />
        ))}
      </div>
      <div className="text-center text-xs text-text-secondary mt-4">
        {t("share.readonly")}
      </div>
    </div>
  )
}
