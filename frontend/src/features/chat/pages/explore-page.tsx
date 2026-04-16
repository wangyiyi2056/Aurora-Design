import { useNavigate } from "react-router-dom"
import { CommentOutlined, DatabaseOutlined, BookOutlined, RobotOutlined, NodeIndexOutlined } from "@ant-design/icons"
import { useTranslation } from "react-i18next"
import { useChatStore } from "@/stores/chat-store"

export default function ExplorePage() {
  const navigate = useNavigate()
  const { resetChat } = useChatStore()
  const { t } = useTranslation("chat")

  const shortcuts = [
    { icon: <CommentOutlined />, label: t("explore.newChat"), desc: t("explore.newChatDesc"), action: "/chat" },
    { icon: <DatabaseOutlined />, label: t("explore.datasource"), desc: t("explore.datasourceDesc"), action: "/construct/database" },
    { icon: <BookOutlined />, label: t("explore.knowledge"), desc: t("explore.knowledgeDesc"), action: "/construct/knowledge" },
    { icon: <RobotOutlined />, label: t("explore.agent"), desc: t("explore.agentDesc"), action: "/construct/skills" },
    { icon: <NodeIndexOutlined />, label: t("explore.awel"), desc: t("explore.awelDesc"), action: "/construct/flow" },
  ]

  const handleClick = (action: string) => {
    if (action === "/chat") resetChat()
    navigate(action)
  }

  return (
    <div className="max-w-4xl mx-auto pt-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-3">{t("explore.title")}</h1>
        <p className="text-text-secondary text-lg">
          {t("explore.subtitle")}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {shortcuts.map((s) => (
          <button
            key={s.label}
            onClick={() => handleClick(s.action)}
            className="flex flex-col items-start gap-2 p-5 rounded-xl bg-surface hover:bg-surface-hover border border-border transition-colors text-left"
            aria-label={s.label}
          >
            <span className="text-primary text-2xl" aria-hidden="true">{s.icon}</span>
            <span className="font-semibold text-base">{s.label}</span>
            <span className="text-text-secondary text-sm">{s.desc}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
