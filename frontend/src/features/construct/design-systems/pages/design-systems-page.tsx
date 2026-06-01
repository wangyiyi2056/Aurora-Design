import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Eye, FileText, Palette, Plus, Search, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createDesignSystem,
  deleteDesignSystem,
  designSystemPreviewUrl,
  getDesignSystem,
  listDesignSystems,
  toggleDesignSystem,
  updateDesignSystem,
  type DesignSystemDetail,
  type DesignSystemSummary,
} from "@/services/design-systems"

type SourceFilter = "all" | "built-in" | "user"
type StatusFilter = "all" | "draft" | "published"

export default function DesignSystemsPage() {
  const queryClient = useQueryClient()
  const systemsQuery = useQuery({
    queryKey: ["design-systems"],
    queryFn: listDesignSystems,
  })
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [source, setSource] = useState<SourceFilter>("all")
  const [status, setStatus] = useState<StatusFilter>("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [draft, setDraft] = useState({
    id: "",
    title: "",
    summary: "",
    category: "Developer Tools",
    body: "",
  })

  const systems = systemsQuery.data ?? []
  const categories = useMemo(
    () => Array.from(new Set(systems.map((system) => system.category).filter(Boolean))).sort(),
    [systems],
  )
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return systems.filter((system) => {
      if (category !== "all" && system.category !== category) return false
      if (source !== "all" && system.source !== source) return false
      if (status !== "all" && system.status !== status) return false
      if (!q) return true
      return [system.title, system.summary, system.category, system.surface, system.source]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(q))
    })
  }, [category, query, source, status, systems])

  const detailQuery = useQuery({
    queryKey: ["design-systems", selectedId],
    queryFn: () => getDesignSystem(selectedId as string),
    enabled: Boolean(selectedId),
  })

  const createMutation = useMutation({
    mutationFn: createDesignSystem,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["design-systems"] })
      setCreateOpen(false)
      setSelectedId(created.id)
      setDraft({ id: "", title: "", summary: "", category: "Developer Tools", body: "" })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateDesignSystem(id, { status }),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["design-systems"] })
      queryClient.setQueryData(["design-systems", updated.id], updated)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: toggleDesignSystem,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["design-systems"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDesignSystem,
    onSuccess: async () => {
      setSelectedId(null)
      await queryClient.invalidateQueries({ queryKey: ["design-systems"] })
    },
  })

  const selected = detailQuery.data ?? null

  function submitCreate() {
    const title = draft.title.trim()
    if (!title) return
    createMutation.mutate({
      id: draft.id.trim() || undefined,
      title,
      summary: draft.summary.trim(),
      category: draft.category.trim() || "Uncategorized",
      body:
        draft.body.trim() ||
        `# ${title}\n\n> Category: ${draft.category.trim() || "Uncategorized"}\n> ${draft.summary.trim()}\n`,
    })
  }

  return (
    <ConstructShell>
      <div className="p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-foreground">设计系统</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              管理可注入聊天生成流程的 DESIGN.md 视觉系统。
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            新建设计系统
          </Button>
        </div>

        <div className="mb-5 grid gap-3 md:grid-cols-[1fr_180px_150px_150px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="搜索设计系统..." className="pl-9" />
          </div>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={category} onChange={(event) => setCategory(event.currentTarget.value)}>
            <option value="all">全部分类</option>
            {categories.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={source} onChange={(event) => setSource(event.currentTarget.value as SourceFilter)}>
            <option value="all">全部来源</option>
            <option value="built-in">内置</option>
            <option value="user">用户</option>
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.currentTarget.value as StatusFilter)}>
            <option value="all">全部状态</option>
            <option value="published">已发布</option>
            <option value="draft">草稿</option>
          </select>
        </div>

        {systemsQuery.isLoading ? (
          <div className="py-10 text-center text-muted-foreground">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="py-10 text-center text-muted-foreground">没有匹配的设计系统</div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((system) => (
              <DesignSystemCard key={system.id} system={system} onOpen={() => setSelectedId(system.id)} onToggle={() => toggleMutation.mutate(system.id)} />
            ))}
          </div>
        )}

        <DesignSystemDetailDialog
          system={selected}
          loading={detailQuery.isLoading}
          onClose={() => setSelectedId(null)}
          onToggleStatus={(system) => updateMutation.mutate({ id: system.id, status: system.status === "published" ? "draft" : "published" })}
          onDelete={(system) => deleteMutation.mutate(system.id)}
          busy={updateMutation.isPending || deleteMutation.isPending}
        />

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="max-w-[760px]">
            <DialogHeader>
              <DialogTitle>新建设计系统</DialogTitle>
            </DialogHeader>
            <div className="grid gap-3">
              <Input value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.currentTarget.value }))} placeholder="标题，例如 Aurora" />
              <Input value={draft.id} onChange={(event) => setDraft((current) => ({ ...current, id: event.currentTarget.value }))} placeholder="可选 ID，例如 aurora" />
              <Input value={draft.category} onChange={(event) => setDraft((current) => ({ ...current, category: event.currentTarget.value }))} placeholder="分类" />
              <Input value={draft.summary} onChange={(event) => setDraft((current) => ({ ...current, summary: event.currentTarget.value }))} placeholder="一句话摘要" />
              <Textarea value={draft.body} onChange={(event) => setDraft((current) => ({ ...current, body: event.currentTarget.value }))} placeholder="可选 DESIGN.md 内容" className="min-h-[220px] font-mono text-xs" />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
              <Button onClick={submitCreate} disabled={createMutation.isPending || !draft.title.trim()}>创建</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ConstructShell>
  )
}

function DesignSystemCard({ system, onOpen, onToggle }: { system: DesignSystemSummary; onOpen: () => void; onToggle: () => void }) {
  return (
    <div role="button" tabIndex={0} onClick={onOpen} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpen() }} className="cursor-pointer rounded-lg border border-border bg-card p-4 text-left transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Palette className="h-4 w-4 text-primary" />
            <h2 className="truncate font-semibold text-foreground">{system.title}</h2>
          </div>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{system.summary || "暂无摘要"}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <span className="whitespace-nowrap text-xs text-muted-foreground">{system.enabled ? "已启用" : "已禁用"}</span>
          <Switch checked={system.enabled} onCheckedChange={onToggle} />
        </div>
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Tag variant="outline">{system.category}</Tag>
        <Tag variant={system.status === "published" ? "success" : "warning"}>{system.status}</Tag>
      </div>
      <div className="flex gap-1">
        {system.swatches.slice(0, 8).map((color) => (
          <span key={color} className="h-6 w-6 rounded-full border border-border" style={{ background: color }} />
        ))}
      </div>
    </div>
  )
}

function DesignSystemDetailDialog({
  system,
  loading,
  onClose,
  onToggleStatus,
  onDelete,
  busy,
}: {
  system: DesignSystemDetail | null
  loading: boolean
  onClose: () => void
  onToggleStatus: (system: DesignSystemDetail) => void
  onDelete: (system: DesignSystemDetail) => void
  busy: boolean
}) {
  return (
    <Dialog open={Boolean(system) || loading} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[980px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            {system?.title ?? "设计系统"}
          </DialogTitle>
        </DialogHeader>
        {loading || !system ? (
          <div className="py-10 text-center text-muted-foreground">加载中...</div>
        ) : (
          <div className="grid max-h-[72vh] gap-4 overflow-auto lg:grid-cols-[1fr_360px]">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Tag variant="outline">{system.category}</Tag>
                <Tag variant={system.enabled ? "success" : "secondary"}>{system.enabled ? "已启用" : "已禁用"}</Tag>
                <Tag variant={system.status === "published" ? "success" : "warning"}>{system.status}</Tag>
              </div>
              <p className="text-sm text-muted-foreground">{system.summary}</p>
              <pre className="max-h-[420px] overflow-auto rounded-lg border border-border bg-muted p-3 text-xs text-foreground">{system.body}</pre>
            </div>
            <div className="space-y-3">
              <div className="overflow-hidden rounded-lg border border-border bg-background">
                <iframe title={`${system.title} preview`} src={designSystemPreviewUrl(system.id)} className="h-[320px] w-full bg-white" />
              </div>
              <div className="rounded-lg border border-border p-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <Eye className="h-4 w-4" />
                  文件包
                </div>
                <div className="max-h-[180px] space-y-1 overflow-auto text-xs text-muted-foreground">
                  {(system.files ?? []).map((file) => (
                    <div key={file.path} className="flex justify-between gap-3">
                      <span className="truncate">{file.path}</span>
                      <span>{file.kind}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
        <DialogFooter>
          {system?.isEditable ? (
            <>
              <Button variant="outline" onClick={() => onToggleStatus(system)} disabled={busy}>
                {system.status === "published" ? "转为草稿" : "发布"}
              </Button>
              <Button variant="destructive" onClick={() => onDelete(system)} disabled={busy} className="gap-2">
                <Trash2 className="h-4 w-4" />
                删除
              </Button>
            </>
          ) : null}
          <Button variant="outline" onClick={onClose}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
