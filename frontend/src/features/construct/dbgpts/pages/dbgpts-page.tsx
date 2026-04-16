import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Card, List, Tabs, Tag } from "antd"
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
  const [activeTab, setActiveTab] = useState("hub")

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
      <Tabs activeKey={activeTab} onChange={setActiveTab} className="mb-4">
        <Tabs.TabPane tab={t("dbgpts.hub")} key="hub">
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, lg: 3 }}
            dataSource={hubItems}
            locale={{ emptyText: t("dbgpts.emptyHub") }}
            renderItem={(item) => (
              <List.Item>
                <Card
                  title={item.name}
                  className="bg-surface border-border w-full"
                  extra={<Tag>v{item.version}</Tag>}
                  actions={[
                    <Button type="primary" size="small" onClick={() => install(item)}>
                      {t("dbgpts.install")}
                    </Button>,
                  ]}
                >
                  <p className="text-text-secondary text-sm m-0">{item.description}</p>
                </Card>
              </List.Item>
            )}
          />
        </Tabs.TabPane>
        <Tabs.TabPane tab={t("dbgpts.my")} key="my">
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, lg: 3 }}
            dataSource={myPlugins}
            locale={{ emptyText: t("dbgpts.emptyMy") }}
            renderItem={(item) => (
              <List.Item>
                <Card
                  title={item.name}
                  className="bg-surface border-border w-full"
                  extra={<Tag color="blue">v{item.version}</Tag>}
                  actions={[
                    <Button danger size="small" onClick={() => uninstall(item.id)}>
                      {t("dbgpts.uninstall")}
                    </Button>,
                  ]}
                >
                  <p className="text-text-secondary text-sm m-0">{item.description}</p>
                </Card>
              </List.Item>
            )}
          />
        </Tabs.TabPane>
      </Tabs>
    </ConstructShell>
  )
}
