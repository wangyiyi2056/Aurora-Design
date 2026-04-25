import { useNavigate } from "react-router-dom"
import { MessageSquare, Database, BookOpen, Bot, Workflow } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useChatStore } from "@/stores/chat-store"

export default function ExplorePage() {
  const navigate = useNavigate()
  const { resetChat } = useChatStore()
  const { t } = useTranslation("chat")

  const shortcuts = [
    { icon: MessageSquare, label: t("explore.newChat"), desc: t("explore.newChatDesc"), action: "/chat" },
    { icon: Database, label: t("explore.datasource"), desc: t("explore.datasourceDesc"), action: "/construct/database" },
    { icon: BookOpen, label: t("explore.knowledge"), desc: t("explore.knowledgeDesc"), action: "/construct/knowledge" },
    { icon: Bot, label: t("explore.agent"), desc: t("explore.agentDesc"), action: "/construct/skills" },
    { icon: Workflow, label: t("explore.awel"), desc: t("explore.awelDesc"), action: "/construct/flow" },
  ]

  const handleClick = (action: string) => {
    if (action === "/chat") resetChat()
    navigate(action)
  }

  return (
    <div className="max-w-4xl mx-auto pt-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-3">{t("explore.title")}</h1>
        <p className="text-muted-foreground text-lg">
          {t("explore.subtitle")}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {shortcuts.map((s) => (
          <button
            key={s.label}
            onClick={() => handleClick(s.action)}
            className="flex flex-col items-start gap-2 p-5 rounded-xl bg-card hover:bg-muted border border-border transition-colors text-left"
            aria-label={s.label}
          >
            <s.icon className="h-6 w-6 text-primary" aria-hidden="true" />
            <span className="font-semibold text-base">{s.label}</span>
            <span className="text-muted-foreground text-sm">{s.desc}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
