import { NavLink, useLocation, useNavigate } from "react-router-dom"
import {
  LayoutGrid,
  MessageSquare,
  ArrowRightToLine,
  ArrowLeftToLine,
  Hammer,
  Globe,
  Sun,
  Moon,
} from "lucide-react"
import { useTranslation } from "react-i18next"
import i18n, { normalizeLanguage } from "@/lib/i18n"
import { useGlobalStore } from "@/stores/global-store"
import { useChatStore } from "@/stores/chat-store"
import { ConversationList } from "@/features/chat/components/conversation-list"
import { BrandLogo } from "@/components/brand/brand-logo"

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, language, setLanguage, theme, setTheme } = useGlobalStore()
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const currentLanguage = normalizeLanguage(language)

  const sessionId = useChatStore((s) => s.sessionId)
  const resetToNewChat = useChatStore((s) => s.resetToNewChat)

  const isConstructActive = [
    "/construct/app",
    "/construct/database",
    "/construct/knowledge",
    "/construct/skills",
    "/construct/models",
  ].some((p) => location.pathname.startsWith(p))

  const navItems = [
    { path: "/", label: t("nav.explore"), icon: LayoutGrid },
    { path: "/chat", label: t("nav.chat"), icon: MessageSquare },
    { path: "/construct/app", label: t("nav.construct"), icon: Hammer },
  ]

  const isChatPage = location.pathname === "/chat"

  const handleNewChat = () => {
    resetToNewChat()
    navigate("/chat")
  }

  return (
    <aside
      data-collapsed={sidebarCollapsed}
      className="flex flex-col border-r border-border bg-surface transition-all duration-fast data-[collapsed='true']:w-16 data-[collapsed='false']:w-[200px]"
    >
      <div className={`flex h-14 items-center border-b border-border px-4 ${sidebarCollapsed ? "justify-center" : ""}`}>
        {sidebarCollapsed ? (
          <BrandLogo className="h-7 w-7" />
        ) : (
          <div className="flex min-w-0 items-center gap-2">
            <BrandLogo className="h-7 w-7" />
            <span className="truncate text-lg font-semibold tracking-tight text-text">
              {t("appName")}
            </span>
          </div>
        )}
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded px-3 py-2 transition-colors ${
                isActive || (item.path === "/construct/app" && isConstructActive)
                  ? "bg-primary text-white"
                  : "text-text-secondary hover:bg-surface-hover hover:text-text"
              } ${sidebarCollapsed ? "justify-center" : ""}`
            }
            title={item.label}
          >
            <item.icon className="h-4 w-4" />
            {!sidebarCollapsed && <span className="text-sm">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {isChatPage && (
        <div className="flex-1 overflow-y-auto border-t border-border">
          <ConversationList
            activeId={sessionId}
            collapsed={sidebarCollapsed}
            onNewChat={handleNewChat}
          />
        </div>
      )}

      <div className="p-3 border-t border-border flex flex-col gap-1">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text w-full ${sidebarCollapsed ? "justify-center" : ""}`}
          aria-label={t("sidebar.toggleTheme")}
          title={t("sidebar.toggleTheme")}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {!sidebarCollapsed && (
            <span>{theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}</span>
          )}
        </button>
        <button
          onClick={() => {
            const next = currentLanguage === "zh-CN" ? "en" : "zh-CN"
            setLanguage(next)
            i18n.changeLanguage(next)
          }}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text w-full ${sidebarCollapsed ? "justify-center" : ""}`}
          aria-label={t("sidebar.toggleLanguage")}
          title={t("sidebar.toggleLanguage")}
        >
          <Globe className="h-4 w-4" />
          {!sidebarCollapsed && <span>{currentLanguage === "zh-CN" ? "中文" : "English"}</span>}
        </button>
        <button
          onClick={toggleSidebar}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text w-full ${sidebarCollapsed ? "justify-center" : ""}`}
          aria-label={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          title={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
        >
          {sidebarCollapsed ? <ArrowRightToLine className="h-4 w-4" /> : <ArrowLeftToLine className="h-4 w-4" />}
          {!sidebarCollapsed && <span>{t("sidebar.collapse")}</span>}
        </button>
      </div>
    </aside>
  )
}
