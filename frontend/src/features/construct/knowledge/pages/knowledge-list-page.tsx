import { useCallback, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import {
  Plus,
  Database,
  FileText,
  Boxes,
  GitBranch,
  Trash2,
  Loader2,
  BookOpen,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  useKnowledgeListV2,
  useKnowledgeDetailV2,
} from "../hooks/use-knowledge-v2"
import { useDeleteKnowledge, useCreateKnowledge } from "../hooks/use-knowledge"

const CHUNK_STRATEGIES = [
  { value: "fixed", labelKey: "knowledge.strategies.fixed" },
  { value: "recursive", labelKey: "knowledge.strategies.recursive" },
  { value: "semantic", labelKey: "knowledge.strategies.semantic" },
]

function KnowledgeCard({
  name,
  onDelete,
}: {
  name: string
  onDelete: (name: string) => void
}) {
  const { t } = useTranslation("construct")
  const navigate = useNavigate()
  const { data: detail } = useKnowledgeDetailV2(name)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  return (
    <Card
      className="group cursor-pointer transition-shadow hover:shadow-md"
      onClick={() => navigate(`/construct/knowledge/${encodeURIComponent(name)}`)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base flex items-center gap-2 truncate">
            <Database className="h-4 w-4 shrink-0 text-primary" />
            <span className="truncate">{name}</span>
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation()
              setDeleteConfirm(true)
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Boxes className="h-3 w-3" />
            <span>{t("knowledge.v2.list.chunks")}</span>
            <span className="ml-auto font-medium tabular-nums text-foreground">
              {detail?.chunks?.toLocaleString() ?? "-"}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <GitBranch className="h-3 w-3" />
            <span>{t("knowledge.v2.list.strategy")}</span>
            <span className="ml-auto font-medium text-foreground">
              {detail?.chunk_strategy ?? "-"}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <FileText className="h-3 w-3" />
            <span>{t("knowledge.v2.list.size")}</span>
            <span className="ml-auto font-medium tabular-nums text-foreground">
              {detail?.chunk_size ?? "-"}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <BookOpen className="h-3 w-3" />
            <span>{t("knowledge.v2.list.overlap")}</span>
            <span className="ml-auto font-medium tabular-nums text-foreground">
              {detail?.chunk_overlap ?? "-"}
            </span>
          </div>
        </div>
      </CardContent>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteConfirm} onOpenChange={setDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("knowledge.v2.list.deleteKb")}</DialogTitle>
            <DialogDescription>
              {t("knowledge.v2.list.deleteKbDesc").replace("{{name}}", name)}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(false)}>
              {t("knowledge.v2.list.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(name)
                setDeleteConfirm(false)
              }}
            >
              {t("knowledge.v2.list.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default function KnowledgeListPage() {
  const { t } = useTranslation("construct")
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: names = [], isLoading } = useKnowledgeListV2()
  const deleteKb = useDeleteKnowledge()
  const createKb = useCreateKnowledge()

  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [newStrategy, setNewStrategy] = useState("fixed")
  const [newSize, setNewSize] = useState(1200)
  const [newOverlap, setNewOverlap] = useState(100)

  const handleDelete = useCallback(
    (name: string) => {
      deleteKb.mutate(name, {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ["knowledge", "v2", "list"] })
        },
      })
    },
    [deleteKb, qc],
  )

  const handleCreate = useCallback(() => {
    if (!newName.trim()) return
    createKb.mutate(
      {
        name: newName.trim(),
        chunk_strategy: newStrategy,
        chunk_size: newSize,
        chunk_overlap: newOverlap,
      },
      {
        onSuccess: (data) => {
          // Invalidate V2 list query so it refetches when user navigates back
          qc.invalidateQueries({ queryKey: ["knowledge", "v2", "list"] })
          setCreateOpen(false)
          setNewName("")
          navigate(
            `/construct/knowledge/${encodeURIComponent(data.name)}`
          )
        },
      }
    )
  }, [newName, newStrategy, newSize, newOverlap, createKb, navigate, qc])

  return (
    <ConstructShell>
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1" />
        <Button
          onClick={() => {
            createKb.reset()
            setCreateOpen(true)
          }}
        >
          <Plus className="mr-1 h-4 w-4" />
          {t("knowledge.v2.list.createKb")}
        </Button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : names.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Database className="h-12 w-12 text-muted-foreground/30 mb-4" />
          <h3 className="text-lg font-medium mb-1">{t("knowledge.v2.list.noKbs")}</h3>
          <p className="text-sm text-muted-foreground mb-4 max-w-md">
            {t("knowledge.v2.list.noKbsDesc")}
          </p>
          <Button
            onClick={() => {
              createKb.reset()
              setCreateOpen(true)
            }}
          >
            <Plus className="mr-1 h-4 w-4" />
            {t("knowledge.v2.list.createKb")}
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {names.map((name) => (
            <KnowledgeCard
              key={name}
              name={name}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* Create Knowledge Base dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("knowledge.v2.list.createKb")}</DialogTitle>
            <DialogDescription>
              {t("knowledge.v2.list.createKbDesc")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Name */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("knowledge.v2.list.name")}</label>
              <Input
                placeholder={t("knowledge.v2.list.namePlaceholder")}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {t("knowledge.v2.list.nameHint")}
              </p>
            </div>

            {/* Chunk strategy */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("knowledge.v2.list.chunkStrategy")}</label>
              <Select value={newStrategy} onValueChange={setNewStrategy}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CHUNK_STRATEGIES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {t(s.labelKey as any)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Chunk size */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">{t("knowledge.v2.list.chunkSize")}</label>
                <span className="text-sm tabular-nums text-muted-foreground">{newSize}</span>
              </div>
              <Slider
                min={128}
                max={2048}
                step={64}
                value={[newSize]}
                onValueChange={([v]) => setNewSize(v)}
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>128</span>
                <span>2048</span>
              </div>
            </div>

            {/* Chunk overlap */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">{t("knowledge.v2.list.chunkOverlap")}</label>
                <span className="text-sm tabular-nums text-muted-foreground">{newOverlap}</span>
              </div>
              <Slider
                min={0}
                max={256}
                step={8}
                value={[newOverlap]}
                onValueChange={([v]) => setNewOverlap(v)}
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>0</span>
                <span>256</span>
              </div>
            </div>
          </div>

          {createKb.isError && (
            <p className="text-sm text-destructive">
              {createKb.error instanceof Error
                ? createKb.error.message
                : t("knowledge.v2.list.createFailed")}
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t("knowledge.v2.list.cancel")}
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!newName.trim() || createKb.isPending}
            >
              {createKb.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-1.5 h-4 w-4" />
              )}
              {t("knowledge.v2.list.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConstructShell>
  )
}
