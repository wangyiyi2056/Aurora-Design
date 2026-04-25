import { useNavigate } from "react-router-dom"
import { ChevronLeft, Plus, Sun, Moon } from "lucide-react"
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
    <header className="flex h-12 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-2">
        {showBack && (
          <button
            onClick={handleBack}
            className="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={t("chat.back", { defaultValue: "Back" })}
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        )}
        <span className="font-medium">{title || t("appName")}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={t("sidebar.toggleTheme", { ns: "common", defaultValue: "Toggle theme" })}
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        {showNewChat && (
          <button
            onClick={onNewChat}
            className="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={t("explore.newChat")}
          >
            <Plus className="h-5 w-5" />
          </button>
        )}
      </div>
    </header>
  )
}
