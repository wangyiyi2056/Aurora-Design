import { useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Card, Input, List, Select, Slider, Tabs, Tag } from "antd"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  useKnowledgeList,
  useUploadKnowledge,
  useQueryKnowledge,
} from "@/features/construct/knowledge/hooks/use-knowledge"

const chunkStrategies = [
  { value: "fixed", labelKey: "knowledge.strategies.fixed" },
  { value: "paragraph", labelKey: "knowledge.strategies.paragraph" },
  { value: "semantic", labelKey: "knowledge.strategies.semantic" },
]

interface ChunkConfig {
  strategy: string
  size: number
  overlap: number
}

export default function KnowledgePage() {
  const { t } = useTranslation("construct")
  const [name, setName] = useState("")
  const [selected, setSelected] = useState("")
  const [query, setQuery] = useState("")
  const [result, setResult] = useState<unknown>(null)
  const [activeTab, setActiveTab] = useState("upload")
  const [chunkConfig, setChunkConfig] = useState<ChunkConfig>({
    strategy: "fixed",
    size: 512,
    overlap: 64,
  })
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: items = [], isLoading } = useKnowledgeList()
  const upload = useUploadKnowledge()
  const asker = useQueryKnowledge()

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file || !name) return
    await upload.mutateAsync({ name, file })
    setName("")
    if (fileRef.current) fileRef.current.value = ""
  }

  const handleAsk = async () => {
    const data = await asker.mutateAsync({ name: selected, query })
    setResult(data)
  }

  return (
    <ConstructShell>
      <Tabs activeKey={activeTab} onChange={setActiveTab} className="mb-4">
        <Tabs.TabPane tab={t("knowledge.bases")} key="upload">
          <div className="flex flex-col gap-4 mb-6">
            <div className="flex gap-3 items-center">
              <Input
                placeholder={t("knowledge.bases")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <input type="file" ref={fileRef} className="text-sm" />
              <Button type="primary" onClick={handleUpload} loading={upload.isPending}>
                {t("knowledge.upload")}
              </Button>
            </div>

            {isLoading && <div className="text-text-secondary text-sm">Loading...</div>}
            <List
              dataSource={items}
              locale={{ emptyText: t("agent.empty") }}
              renderItem={(it) => (
                <List.Item className="bg-surface rounded-lg border border-border px-4 mb-2">
                  <div className="font-medium text-sm">{it}</div>
                </List.Item>
              )}
            />
          </div>
        </Tabs.TabPane>

        <Tabs.TabPane tab={t("knowledge.query")} key="query">
          <div className="flex flex-col gap-3 mb-4">
            <div className="flex gap-3">
              <Select
                className="min-w-[180px]"
                placeholder={t("knowledge.selectBase")}
                value={selected || undefined}
                onChange={(v) => setSelected(v)}
                options={items.map((it) => ({ value: it, label: it }))}
              />
              <Input
                className="flex-1"
                placeholder={t("knowledge.query")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Button type="primary" onClick={handleAsk} loading={asker.isPending}>
                {t("knowledge.ask")}
              </Button>
            </div>
            {result !== null && (
              <pre className="bg-surface p-3 rounded-lg text-xs overflow-auto max-h-96">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </Tabs.TabPane>

        <Tabs.TabPane tab={t("knowledge.chunking")} key="chunking">
          <Card className="bg-surface border-border mb-4">
            <p className="text-text-secondary text-sm m-0 mb-4">
              {t("knowledge.chunkingDesc")}
            </p>
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <span className="text-sm w-20">{t("knowledge.strategy")}</span>
                <Select
                  className="w-48"
                  value={chunkConfig.strategy}
                  onChange={(v) => setChunkConfig((c) => ({ ...c, strategy: v }))}
                  options={chunkStrategies.map((s) => ({
                    value: s.value,
                    label: t(s.labelKey),
                  }))}
                />
                <Tag color="blue">{t("knowledge.strategies.fixed")}</Tag>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm w-20">{t("knowledge.chunkSize")}</span>
                <Slider
                  className="flex-1"
                  min={128}
                  max={2048}
                  step={128}
                  value={chunkConfig.size}
                  onChange={(v) => setChunkConfig((c) => ({ ...c, size: v }))}
                />
                <span className="text-sm w-16 text-right">{chunkConfig.size}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm w-20">{t("knowledge.chunkOverlap")}</span>
                <Slider
                  className="flex-1"
                  min={0}
                  max={256}
                  step={16}
                  value={chunkConfig.overlap}
                  onChange={(v) => setChunkConfig((c) => ({ ...c, overlap: v }))}
                />
                <span className="text-sm w-16 text-right">{chunkConfig.overlap}</span>
              </div>
            </div>
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab={t("knowledge.graph")} key="graph">
          <Card className="bg-surface border-border">
            <p className="text-text-secondary text-sm m-0 mb-4">
              {t("knowledge.graphDesc")}
            </p>
            <div className="relative h-64 bg-surface rounded-lg border border-border border-dashed flex items-center justify-center overflow-hidden">
              <div className="absolute inset-0 opacity-30">
                <svg className="w-full h-full" viewBox="0 0 400 200">
                  <circle cx="80" cy="60" r="8" fill="currentColor" />
                  <circle cx="200" cy="40" r="10" fill="currentColor" />
                  <circle cx="320" cy="80" r="8" fill="currentColor" />
                  <circle cx="140" cy="140" r="8" fill="currentColor" />
                  <circle cx="280" cy="160" r="8" fill="currentColor" />
                  <line x1="80" y1="60" x2="200" y2="40" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="200" y1="40" x2="320" y2="80" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="80" y1="60" x2="140" y2="140" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="140" y1="140" x2="280" y2="160" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="320" y1="80" x2="280" y2="160" stroke="currentColor" strokeWidth="1.5" />
                </svg>
              </div>
              <div className="relative z-10 flex gap-6">
                <div className="text-center">
                  <div className="text-2xl font-semibold">12</div>
                  <div className="text-xs text-text-secondary">{t("knowledge.entities")}</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-semibold">8</div>
                  <div className="text-xs text-text-secondary">{t("knowledge.relations")}</div>
                </div>
              </div>
            </div>
          </Card>
        </Tabs.TabPane>
      </Tabs>
    </ConstructShell>
  )
}
