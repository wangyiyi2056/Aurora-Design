import { useLocation, useNavigate } from "react-router-dom"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  ]

  // Find the matching key for current path
  const currentKey = items.find(item => location.pathname.startsWith(item.key))?.key || "/construct/app"

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mt-0 mb-4">{t("construct.title")}</h2>
      <Tabs value={currentKey} onValueChange={(key) => navigate(key)} className="mb-4">
        <TabsList>
          {items.map((item) => (
            <TabsTrigger key={item.key} value={item.key}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {children}
    </div>
  )
}