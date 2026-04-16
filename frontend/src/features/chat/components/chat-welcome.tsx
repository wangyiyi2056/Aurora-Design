import { CommentOutlined, DatabaseOutlined, BookOutlined, RobotOutlined } from "@ant-design/icons"
import { useTranslation } from "react-i18next"

interface ChatWelcomeProps {
  onSelect: (prompt: string) => void
}

export function ChatWelcome({ onSelect }: ChatWelcomeProps) {
  const { t } = useTranslation("chat")

  const examples = [
    { icon: <DatabaseOutlined />, label: t("explore.datasource"), prompt: "Show me total sales by region" },
    { icon: <BookOutlined />, label: t("explore.knowledge"), prompt: "What does our privacy policy say about cookies?" },
    { icon: <RobotOutlined />, label: t("explore.agent"), prompt: "Analyze the dataset and generate insights" },
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-white text-3xl shadow-lg">
        <CommentOutlined />
      </div>
      <div>
        <h3 className="text-2xl font-semibold m-0 mb-1">{t("chat.welcomeTitle")}</h3>
        <p className="text-text-secondary m-0">{t("chat.welcomeDesc")}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl">
        {examples.map((ex) => (
          <button
            key={ex.label}
            onClick={() => onSelect(ex.prompt)}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-surface hover:bg-surface-hover border border-border transition-colors text-sm"
            aria-label={ex.label}
          >
            <span className="text-primary text-lg" aria-hidden="true">{ex.icon}</span>
            <span className="font-medium">{ex.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
