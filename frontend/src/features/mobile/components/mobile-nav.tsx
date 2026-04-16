import { useNavigate } from "react-router-dom"
import { LeftOutlined, PlusOutlined, SunOutlined, MoonOutlined } from "@ant-design/icons"
import { useTranslation } from "react-i18next"
import { useGlobalStore } from "@/stores/global-store"

interface MobileNavProps {
  title?: string
  showBack?: boolean
  onBack?: () => void
  showNewChat?: boolean
  onNewChat?: () => void
}

export function MobileNav({
  title,
  showBack = true,
  onBack,
  showNewChat = false,
  onNewChat,
}: MobileNavProps) {
  const navigate = useNavigate()
  const { t } = useTranslation("chat")
  const { theme, setTheme } = useGlobalStore()

  const handleBack = () => {
    if (onBack) {
      onBack()
    } else {
      navigate(-1)
    }
  }

  return (
    <header className="flex h-12 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-2">
        {showBack && (
          <button
            onClick={handleBack}
            className="flex h-8 w-8 items-center justify-center rounded text-text-secondary hover:bg-surface-hover hover:text-text"
            aria-label={t("chat.back", { defaultValue: "Back" })}
          >
            <LeftOutlined />
          </button>
        )}
        <span className="font-medium">{title || t("appName")}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex h-8 w-8 items-center justify-center rounded text-text-secondary hover:bg-surface-hover hover:text-text"
          aria-label={t("sidebar.toggleTheme", { ns: "common", defaultValue: "Toggle theme" })}
        >
          {theme === "dark" ? <SunOutlined /> : <MoonOutlined />}
        </button>
        {showNewChat && (
          <button
            onClick={onNewChat}
            className="flex h-8 w-8 items-center justify-center rounded text-text-secondary hover:bg-surface-hover hover:text-text"
            aria-label={t("explore.newChat")}
          >
            <PlusOutlined />
          </button>
        )}
      </div>
    </header>
  )
}
