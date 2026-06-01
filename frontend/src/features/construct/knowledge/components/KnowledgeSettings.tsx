// @ts-nocheck
import { useCallback, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  AlertTriangle,
  Save,
  Trash2,
  Eraser,
  Database,
  FileText,
  Boxes,
  GitBranch,
  Calendar,
  Loader2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import {
  useKnowledgeDetailV2,
  useClearCache,
  useDeleteDocuments,
  useDocumentsPaginated,
} from "../hooks/use-knowledge-v2"
import { useDeleteKnowledge } from "../hooks/use-knowledge"

interface KnowledgeSettingsProps {
  knowledgeName: string
}

const CHUNK_STRATEGIES = [
  { value: "fixed", label: "Fixed Size" },
  { value: "recursive", label: "Recursive" },
  { value: "semantic", label: "Semantic" },
]

export function KnowledgeSettings({ knowledgeName }: KnowledgeSettingsProps) {
  const navigate = useNavigate()

  const { data: detail } = useKnowledgeDetailV2(knowledgeName)
  const clearCacheMutation = useClearCache()
  const deleteKb = useDeleteKnowledge()
  const deleteDocsMutation = useDeleteDocuments()
  const { data: allDocs } = useDocumentsPaginated(knowledgeName, {
    page: 1,
    page_size: 200,
  })

  // Chunk config state
  const [chunkStrategy, setChunkStrategy] = useState(
    detail?.chunk_strategy || "fixed",
  )
  const [chunkSize, setChunkSize] = useState(detail?.chunk_size || 1200)
  const [chunkOverlap, setChunkOverlap] = useState(detail?.chunk_overlap || 100)

  // Confirmation dialogs
  const [clearCacheConfirm, setClearCacheConfirm] = useState(false)
  const [clearQueryCacheConfirm, setClearQueryCacheConfirm] = useState(false)
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false)
  const [deleteKbConfirm, setDeleteKbConfirm] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const handleSaveChunkConfig = useCallback(() => {
    // Persist chunk config locally per knowledge base (backend scoping planned)
    const key = `kb-chunk-config-${knowledgeName}`
    localStorage.setItem(
      key,
      JSON.stringify({ strategy: chunkStrategy, size: chunkSize, overlap: chunkOverlap }),
    )
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 2000)
  }, [knowledgeName, chunkStrategy, chunkSize, chunkOverlap])

  const handleClearLlmCache = useCallback(() => {
    clearCacheMutation.mutate(
      { name: knowledgeName },
      { onSuccess: () => setClearCacheConfirm(false) },
    )
  }, [knowledgeName, clearCacheMutation])

  const handleClearQueryCache = useCallback(() => {
    clearCacheMutation.mutate(
      { name: knowledgeName },
      { onSuccess: () => setClearQueryCacheConfirm(false) },
    )
  }, [knowledgeName, clearCacheMutation])

  const handleDeleteAllDocuments = useCallback(() => {
    const docIds = (allDocs?.items ?? []).map((d) => d.id)
    if (docIds.length === 0) {
      setDeleteAllConfirm(false)
      return
    }
    deleteDocsMutation.mutate(
      { name: knowledgeName, docIds },
      { onSuccess: () => setDeleteAllConfirm(false) },
    )
  }, [knowledgeName, allDocs, deleteDocsMutation])

  const handleDeleteKnowledgeBase = useCallback(() => {
    deleteKb.mutate(knowledgeName, {
      onSuccess: () => {
        setDeleteKbConfirm(false)
        navigate("/construct/knowledge")
      },
    })
  }, [knowledgeName, deleteKb, navigate])

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Knowledge base info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Database className="h-4 w-4" />
            Knowledge Base Info
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Database className="h-3 w-3" /> Name
              </span>
              <p className="text-sm font-medium">{knowledgeName}</p>
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <FileText className="h-3 w-3" /> Documents
              </span>
              <p className="text-sm font-medium tabular-nums">
                {detail?.chunks !== undefined ? "Available" : "-"}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Boxes className="h-3 w-3" /> Chunks
              </span>
              <p className="text-sm font-medium tabular-nums">
                {detail?.chunks?.toLocaleString() ?? "-"}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <GitBranch className="h-3 w-3" /> Chunk Strategy
              </span>
              <p className="text-sm font-medium">
                {detail?.chunk_strategy || "-"}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="h-3 w-3" /> Collection
              </span>
              <p className="text-sm text-muted-foreground truncate" title={detail?.collection_name}>
                {detail?.collection_name || "-"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Chunk configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Chunk Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <span className="text-sm w-28 shrink-0">Strategy</span>
            <Select
              value={chunkStrategy}
              onValueChange={setChunkStrategy}
            >
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHUNK_STRATEGIES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm w-28 shrink-0">Chunk Size</span>
            <Slider
              className="flex-1"
              min={128}
              max={2048}
              step={64}
              value={[chunkSize]}
              onValueChange={([v]) => setChunkSize(v)}
            />
            <span className="text-sm w-14 text-right tabular-nums">{chunkSize}</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm w-28 shrink-0">Overlap</span>
            <Slider
              className="flex-1"
              min={0}
              max={256}
              step={8}
              value={[chunkOverlap]}
              onValueChange={([v]) => setChunkOverlap(v)}
            />
            <span className="text-sm w-14 text-right tabular-nums">{chunkOverlap}</span>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={handleSaveChunkConfig} size="sm">
              {saveSuccess ? (
                <>Saved</>
              ) : (
                <>
                  <Save className="mr-1 h-3.5 w-3.5" />
                  Save Configuration
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Cache management */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cache Management</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">LLM Response Cache</p>
              <p className="text-xs text-muted-foreground">
                Clear cached LLM responses to force regeneration
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setClearCacheConfirm(true)}
            >
              <Eraser className="mr-1 h-3.5 w-3.5" />
              Clear LLM Cache
            </Button>
          </div>
          <div className="flex items-center justify-between border-t pt-3">
            <div>
              <p className="text-sm font-medium">Query Cache</p>
              <p className="text-xs text-muted-foreground">
                Clear cached query results
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setClearQueryCacheConfirm(true)}
            >
              <Eraser className="mr-1 h-3.5 w-3.5" />
              Clear Query Cache
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-base text-destructive flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Danger Zone
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete All Documents</p>
              <p className="text-xs text-muted-foreground">
                Remove all documents from this knowledge base
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setDeleteAllConfirm(true)}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete All
            </Button>
          </div>
          <div className="flex items-center justify-between border-t pt-3">
            <div>
              <p className="text-sm font-medium">Delete Knowledge Base</p>
              <p className="text-xs text-muted-foreground">
                Permanently delete this knowledge base and all its data
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setDeleteKbConfirm(true)}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation dialogs */}
      <Dialog open={clearCacheConfirm} onOpenChange={setClearCacheConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear LLM Cache</DialogTitle>
            <DialogDescription>
              This will clear all cached LLM responses. Future queries will regenerate
              responses. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearCacheConfirm(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleClearLlmCache}
              disabled={clearCacheMutation.isPending}
            >
              {clearCacheMutation.isPending ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Clear Cache
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={clearQueryCacheConfirm} onOpenChange={setClearQueryCacheConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear Query Cache</DialogTitle>
            <DialogDescription>
              This will clear all cached query results. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearQueryCacheConfirm(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleClearQueryCache}
              disabled={clearCacheMutation.isPending}
            >
              {clearCacheMutation.isPending ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Clear Cache
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteAllConfirm} onOpenChange={setDeleteAllConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete All Documents</DialogTitle>
            <DialogDescription>
              This will permanently delete all documents in "{knowledgeName}".
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteAllConfirm(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAllDocuments}
            >
              Delete All Documents
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteKbConfirm} onOpenChange={setDeleteKbConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Knowledge Base</DialogTitle>
            <DialogDescription>
              This will permanently delete the knowledge base "{knowledgeName}" and all
              its documents, chunks, entities, and relationships. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteKbConfirm(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteKnowledgeBase}
              disabled={deleteKb.isPending}
            >
              {deleteKb.isPending ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Delete Knowledge Base
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
