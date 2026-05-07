import { useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tag } from "@/components/ui/tag"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
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
    await upload.mutateAsync({ name, file, chunkConfig })
    setName("")
    if (fileRef.current) fileRef.current.value = ""
  }

  const handleAsk = async () => {
    const data = await asker.mutateAsync({ name: selected, query })
    setResult(data)
  }

  return (
    <ConstructShell>
      <Tabs defaultValue="upload" className="mb-4">
        <TabsList>
          <TabsTrigger value="upload">{t("knowledge.bases")}</TabsTrigger>
          <TabsTrigger value="query">{t("knowledge.query")}</TabsTrigger>
          <TabsTrigger value="chunking">{t("knowledge.chunking")}</TabsTrigger>
          <TabsTrigger value="graph">{t("knowledge.graph")}</TabsTrigger>
        </TabsList>

        <TabsContent value="upload">
          <div className="flex flex-col gap-4 mb-6">
            <div className="flex gap-3 items-center flex-wrap">
              <Input
                placeholder={t("knowledge.bases")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <input type="file" ref={fileRef} className="text-sm" />
              <Button onClick={handleUpload} disabled={upload.isPending}>
                {upload.isPending ? "Uploading..." : t("knowledge.upload")}
              </Button>
            </div>

            {isLoading && <div className="text-muted-foreground text-sm">Loading...</div>}
            <div className="space-y-2">
              {items.map((it) => (
                <div key={it} className="bg-card rounded-lg border border-border px-4 py-3">
                  <div className="font-medium text-sm">{it}</div>
                </div>
              ))}
              {items.length === 0 && !isLoading && (
                <div className="text-muted-foreground text-sm text-center py-8">
                  {t("agent.empty") || "暂无知识库"}
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="query">
          <div className="flex flex-col gap-3 mb-4">
            <div className="flex gap-3 flex-wrap">
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger className="min-w-[180px]">
                  <SelectValue placeholder={t("knowledge.selectBase")} />
                </SelectTrigger>
                <SelectContent>
                  {items.map((it) => (
                    <SelectItem key={it} value={it}>
                      {it}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                className="flex-1 min-w-[150px]"
                placeholder={t("knowledge.query")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Button onClick={handleAsk} disabled={asker.isPending}>
                {asker.isPending ? "Querying..." : t("knowledge.ask")}
              </Button>
            </div>
            {result !== null && (
              <pre className="bg-card p-3 rounded-lg text-xs overflow-auto max-h-96 border border-border">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </TabsContent>

        <TabsContent value="chunking">
          <Card className="p-4 mb-4">
            <p className="text-muted-foreground text-sm m-0 mb-4">
              {t("knowledge.chunkingDesc")}
            </p>
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-sm w-20">{t("knowledge.strategy")}</span>
                <Select
                  value={chunkConfig.strategy}
                  onValueChange={(v) => setChunkConfig((c) => ({ ...c, strategy: v }))}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {chunkStrategies.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {t(s.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Tag variant="info">{t("knowledge.strategies.fixed")}</Tag>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm w-20">{t("knowledge.chunkSize")}</span>
                <Slider
                  className="flex-1"
                  min={128}
                  max={2048}
                  step={128}
                  value={[chunkConfig.size]}
                  onValueChange={(v) => setChunkConfig((c) => ({ ...c, size: v[0] }))}
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
                  value={[chunkConfig.overlap]}
                  onValueChange={(v) => setChunkConfig((c) => ({ ...c, overlap: v[0] }))}
                />
                <span className="text-sm w-16 text-right">{chunkConfig.overlap}</span>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="graph">
          <Card className="p-4">
            <p className="text-muted-foreground text-sm m-0 mb-4">
              {t("knowledge.graphDesc")}
            </p>
            <div className="relative h-64 bg-card rounded-lg border border-border border-dashed flex items-center justify-center overflow-hidden">
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
                  <div className="text-xs text-muted-foreground">{t("knowledge.entities")}</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-semibold">8</div>
                  <div className="text-xs text-muted-foreground">{t("knowledge.relations")}</div>
                </div>
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </ConstructShell>
  )
}
