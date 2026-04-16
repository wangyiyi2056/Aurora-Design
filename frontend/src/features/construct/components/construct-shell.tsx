import { useLocation, useNavigate } from "react-router-dom"
import { Tabs } from "antd"
import { useTranslation } from "react-i18next"

interface ConstructShellProps {
  children: React.ReactNode
}

export function ConstructShell({ children }: ConstructShellProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation("construct")

  const items = [
    { key: "/construct/app", label: t("construct.app") },
    { key: "/construct/database", label: t("construct.database") },
    { key: "/construct/knowledge", label: t("construct.knowledge") },
    { key: "/construct/skills", label: t("construct.skills") },
    { key: "/construct/models", label: t("construct.models") },
    { key: "/construct/flow", label: t("construct.flow") },
    { key: "/construct/prompt", label: t("construct.prompt") },
    { key: "/construct/dbgpts", label: t("construct.dbgpts") },
  ]

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mt-0 mb-4">{t("construct.title")}</h2>
      <Tabs
        activeKey={location.pathname}
        items={items}
        onChange={(key) => navigate(key)}
        className="mb-4"
      />
      {children}
    </div>
  )
}
