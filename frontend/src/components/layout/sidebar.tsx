import { NavLink, useLocation } from "react-router-dom"
import {
  CommentOutlined,
  AppstoreOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BuildOutlined,
  GlobalOutlined,
  SunOutlined,
  MoonOutlined,
} from "@ant-design/icons"
import { useTranslation } from "react-i18next"
import i18n from "@/lib/i18n"
import { useGlobalStore } from "@/stores/global-store"

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, language, setLanguage, theme, setTheme } = useGlobalStore()
  const location = useLocation()
  const { t } = useTranslation()

  const isConstructActive = [
    "/construct/app",
    "/construct/database",
    "/construct/knowledge",
    "/construct/skills",
    "/construct/models",
    "/construct/flow",
    "/construct/prompt",
    "/construct/dbgpts",
  ].some((p) => location.pathname.startsWith(p))

  const navItems = [
    { path: "/", label: t("nav.explore"), icon: <AppstoreOutlined /> },
    { path: "/chat", label: t("nav.chat"), icon: <CommentOutlined /> },
    { path: "/construct/app", label: t("nav.construct"), icon: <BuildOutlined /> },
  ]

  return (
    <aside
      data-collapsed={sidebarCollapsed}
      className="flex flex-col border-r border-border bg-surface transition-all duration-fast data-[collapsed='true']:w-16 data-[collapsed='false']:w-[200px]"
    >
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        {!sidebarCollapsed && (
          <span className="text-lg font-semibold tracking-tight text-text">
            {t("appName")}
          </span>
        )}
        <button
          onClick={toggleSidebar}
          className="flex h-8 w-8 items-center justify-center rounded text-text-secondary transition-colors hover:bg-surface-hover hover:text-text"
          aria-label={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          title={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
        >
          {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
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
            <span className="text-base">{item.icon}</span>
            {!sidebarCollapsed && <span className="text-sm">{item.label}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-border flex flex-col gap-1">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text w-full ${sidebarCollapsed ? "justify-center" : ""}`}
          aria-label={t("sidebar.toggleTheme")}
          title={t("sidebar.toggleTheme")}
        >
          {theme === "dark" ? <SunOutlined /> : <MoonOutlined />}
          {!sidebarCollapsed && (
            <span>{theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}</span>
          )}
        </button>
        <button
          onClick={() => {
            const next = language === "zh" ? "en" : "zh"
            setLanguage(next)
            i18n.changeLanguage(next)
          }}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text w-full ${sidebarCollapsed ? "justify-center" : ""}`}
          aria-label={t("sidebar.toggleLanguage")}
          title={t("sidebar.toggleLanguage")}
        >
          <GlobalOutlined />
          {!sidebarCollapsed && <span>{language === "zh" ? "中文" : "English"}</span>}
        </button>
      </div>
    </aside>
  )
}
