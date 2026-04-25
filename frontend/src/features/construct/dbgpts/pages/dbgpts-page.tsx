import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tag } from "@/components/ui/tag"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { ConstructShell } from "@/features/construct/components/construct-shell"

interface PluginItem {
  id: string
  name: string
  version: string
  description: string
  installed?: boolean
}

const hubData: PluginItem[] = [
  { id: "1", name: "db-summary", version: "1.0.0", description: "Auto-generate database summaries." },
  { id: "2", name: "sql-tuner", version: "0.2.1", description: "SQL performance tuning assistant." },
]

export default function DbgptsPage() {
  const { t } = useTranslation("construct")
  const [myPlugins, setMyPlugins] = useState<PluginItem[]>([
    { id: "3", name: "chart-renderer", version: "1.1.0", description: "Render charts from natural language.", installed: true },
  ])

  const install = (plugin: PluginItem) => {
    if (!myPlugins.find((p) => p.id === plugin.id)) {
      setMyPlugins((prev) => [...prev, { ...plugin, installed: true }])
    }
  }

  const uninstall = (id: string) => {
    setMyPlugins((prev) => prev.filter((p) => p.id !== id))
  }

  const hubItems = hubData.filter((p) => !myPlugins.find((mp) => mp.id === p.id))

  return (
    <ConstructShell>
      <Tabs defaultValue="hub" className="mb-4">
        <TabsList>
          <TabsTrigger value="hub">{t("dbgpts.hub")}</TabsTrigger>
          <TabsTrigger value="my">{t("dbgpts.my")}</TabsTrigger>
        </TabsList>

        <TabsContent value="hub">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {hubItems.map((item) => (
              <Card key={item.id} className="p-4 flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">{item.name}</h4>
                  <Tag variant="outline">v{item.version}</Tag>
                </div>
                <p className="text-muted-foreground text-sm m-0 mb-4 flex-1">{item.description}</p>
                <Button size="sm" onClick={() => install(item)}>
                  {t("dbgpts.install")}
                </Button>
              </Card>
            ))}
            {hubItems.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8 col-span-full">
                {t("dbgpts.emptyHub")}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="my">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {myPlugins.map((item) => (
              <Card key={item.id} className="p-4 flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">{item.name}</h4>
                  <Tag variant="info">v{item.version}</Tag>
                </div>
                <p className="text-muted-foreground text-sm m-0 mb-4 flex-1">{item.description}</p>
                <Button size="sm" variant="destructive" onClick={() => uninstall(item.id)}>
                  {t("dbgpts.uninstall")}
                </Button>
              </Card>
            ))}
            {myPlugins.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8 col-span-full">
                {t("dbgpts.emptyMy")}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </ConstructShell>
  )
}
