import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { useProviderStore } from "@/stores/provider-store"
import {
  Upload,
  FileText,
  Trash2,
  RotateCcw,
  Eraser,
  X,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Info,
  Settings2,
} from "lucide-react"
import { UploadDialog } from "./UploadDialog"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { StatusBadge } from "./StatusBadge"
import {
  useKnowledgeDocumentsV2,
  useStatusCounts,
  useUploadDocument,
  useInsertText,
  useDeleteDocuments,
  useClearCache,
  useReprocessFailed,
  useCancelPipeline,
} from "../hooks/use-knowledge-v2"
import type { DocStatus, DocStatusInfo, DocumentsRequest } from "@/services/knowledge-v2"

interface DocumentManagerProps {
  knowledgeName: string
}

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]


export function DocumentManager({ knowledgeName }: DocumentManagerProps) {
  const navigate = useNavigate()

  // State
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [sortField, setSortField] = useState("created_at")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc")
  const [isDragging, setIsDragging] = useState(false)
  const [textDialogOpen, setTextDialogOpen] = useState(false)
  const [textContent, setTextContent] = useState("")
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [deleteConfirmDoc, setDeleteConfirmDoc] = useState<DocStatusInfo | null>(null)
  const [deleteFile, setDeleteFile] = useState(false)
  const [deleteLlmCache, setDeleteLlmCache] = useState(false)
  const [detailDoc, setDetailDoc] = useState<DocStatusInfo | null>(null)
  const [uploadErrors, setUploadErrors] = useState<Array<{ file: string; error: string }>>([])
  const [processingDeleteDoc, setProcessingDeleteDoc] = useState<DocStatusInfo | null>(null)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Model readiness check
  // Chat model: backend confirms LLM is registered (CLI/BYOK auto-saved to backend)
  // Embedding: frontend flag (Ollama is local, tested via connection test)
  const { data: readiness } = useQuery({
    queryKey: ["models", "readiness"],
    queryFn: () => import("@/services/models").then((m) => m.getModelReadiness()),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
  const embeddingTested = useProviderStore((s) => s.embeddingTested)

  const chatModelReady = readiness?.llm ?? false
  const embeddingModelReady = embeddingTested

  const isModelReady = chatModelReady && embeddingModelReady

  // Build request params
  const docsRequest = useMemo<DocumentsRequest>(() => {
    const req: DocumentsRequest = {
      page,
      page_size: pageSize,
      sort_field: sortField,
      sort_direction: sortDirection,
    }
    if (statusFilter !== "all") {
      req.status_filters = [statusFilter as DocStatus]
    }
    return req
  }, [page, pageSize, sortField, sortDirection, statusFilter])

  // Queries
  const { data: docsData, isLoading: docsLoading } = useKnowledgeDocumentsV2(
    knowledgeName,
    docsRequest,
  )
  const { data: statusCounts } = useStatusCounts(knowledgeName)

  // Mutations
  const uploadDoc = useUploadDocument()
  const insertTextMutation = useInsertText()
  const deleteDocs = useDeleteDocuments()
  const clearCacheMutation = useClearCache()
  const reprocess = useReprocessFailed()
  const cancelPipeline = useCancelPipeline()

  // Derived state
  const documents = docsData?.items ?? []
  const totalDocs = docsData?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(totalDocs / pageSize))

  // ── Drag & Drop handlers ──────────────────────────────────────────────────

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.currentTarget === e.target) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleUploadError = useCallback((fileName: string, error: unknown) => {
    const message =
      error instanceof Error
        ? error.message
        : typeof error === "object" && error !== null && "message" in error
          ? String((error as { message: unknown }).message)
          : "Upload failed. Please try again."
    setUploadErrors((prev) => [...prev, { file: fileName, error: message }])
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      const files = e.dataTransfer.files
      if (files.length > 0) {
        Array.from(files).forEach((file) => {
          uploadDoc.mutate(
            { name: knowledgeName, file },
            {
              onError: (err) => handleUploadError(file.name, err),
            },
          )
        })
      }
    },
    [knowledgeName, uploadDoc, handleUploadError],
  )

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files && files.length > 0) {
        Array.from(files).forEach((file) => {
          uploadDoc.mutate(
            { name: knowledgeName, file },
            {
              onError: (err) => handleUploadError(file.name, err),
            },
          )
        })
      }
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    },
    [knowledgeName, uploadDoc, handleUploadError],
  )

  const handleInsertText = useCallback(() => {
    if (!textContent.trim()) return
    insertTextMutation.mutate(
      { name: knowledgeName, text: textContent.trim() },
      {
        onSuccess: () => {
          setTextContent("")
          setTextDialogOpen(false)
        },
      },
    )
  }, [knowledgeName, textContent, insertTextMutation])

  // Statuses that indicate a document is actively being processed
  const isProcessingStatus = (status: DocStatus) =>
    ["PARSING", "ANALYZING", "PREPROCESSED", "PROCESSING"].includes(status)

  const handleDeleteDoc = useCallback(
    (docId: string, doc?: DocStatusInfo) => {
      // If the document is being processed, show the warning dialog instead
      if (doc && isProcessingStatus(doc.status)) {
        setProcessingDeleteDoc(doc)
        setDeleteConfirmId(null)
        setDeleteConfirmDoc(null)
        return
      }
      deleteDocs.mutate(
        {
          name: knowledgeName,
          docIds: [docId],
          deleteFile,
          deleteLlmCache,
        },
        {
          onSuccess: () => {
            setDeleteConfirmId(null)
            setDeleteConfirmDoc(null)
            setDeleteFile(false)
            setDeleteLlmCache(false)
          },
        },
      )
    },
    [knowledgeName, deleteDocs, deleteFile, deleteLlmCache],
  )

  const handleForceDelete = useCallback(() => {
    if (!processingDeleteDoc) return
    // Cancel the pipeline first, then force delete
    cancelPipeline.mutate(
      { name: knowledgeName },
      {
        onSuccess: () => {
          // Small delay to let the pipeline cancel propagate
          setTimeout(() => {
            deleteDocs.mutate(
              { name: knowledgeName, docIds: [processingDeleteDoc.id], force: true },
              { onSuccess: () => setProcessingDeleteDoc(null) },
            )
          }, 500)
        },
      },
    )
  }, [knowledgeName, processingDeleteDoc, cancelPipeline, deleteDocs])

  const handleClearCache = useCallback(() => {
    if (window.confirm("Clear LLM cache? This cannot be undone.")) {
      clearCacheMutation.mutate({ name: knowledgeName })
    }
  }, [knowledgeName, clearCacheMutation])

  const handleReprocess = useCallback(() => {
    reprocess.mutate({ name: knowledgeName })
  }, [knowledgeName, reprocess])

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-"
    try {
      return new Date(dateStr).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateStr
    }
  }

  const truncatePath = (path: string, maxLen = 40) => {
    if (!path || path.length <= maxLen) return path || "-"
    return "..." + path.slice(-(maxLen - 3))
  }

  const SortableHeader = ({
    field,
    children,
    className,
  }: {
    field: string
    children: React.ReactNode
    className?: string
  }) => (
    <TableHead
      className={cn("cursor-pointer select-none hover:text-foreground transition-colors", className)}
      onClick={() => {
        if (sortField === field) {
          setSortDirection(sortDirection === "asc" ? "desc" : "asc")
        } else {
          setSortField(field)
          setSortDirection("desc")
        }
      }}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {sortField === field && (
          <span className="text-primary">{sortDirection === "desc" ? "↓" : "↑"}</span>
        )}
      </span>
    </TableHead>
  )

  return (
    <div className="flex flex-col gap-3">
      {/* Hidden file input (kept for internal drag-drop on table area) */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFileSelect}
        disabled={!isModelReady}
      />

      {/* Model readiness warning */}
      {!isModelReady && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950/30">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
              模型未就绪，无法上传文件
            </p>
            <div className="mt-1 space-y-0.5 text-xs text-amber-700 dark:text-amber-400">
              {!chatModelReady && (
                <p>· Chat Model 未绑定 — 用于实体和关系抽取（请在「本机 CLI」或「BYOK API」中配置）</p>
              )}
              {!embeddingModelReady && (
                <p>· Embedding Model 未测试连接 — 用于文档向量化（请在「Embedding」Tab 中测试连接）</p>
              )}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/construct/models")}
          >
            <Settings2 className="mr-1.5 h-3.5 w-3.5" />
            绑定模型
          </Button>
        </div>
      )}

      {/* Upload errors */}
      {uploadErrors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30">
          <div className="flex items-center justify-between px-4 py-2 border-b border-red-200 dark:border-red-800">
            <div className="flex items-center gap-2 text-sm font-medium text-red-800 dark:text-red-300">
              <AlertTriangle className="h-4 w-4" />
              上传失败 ({uploadErrors.length})
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-red-600 hover:text-red-800 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900/50"
              onClick={() => setUploadErrors([])}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
          <div className="px-4 py-2 space-y-1.5">
            {uploadErrors.map((err, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-red-700 dark:text-red-400">
                <FileText className="h-3 w-3 mt-0.5 shrink-0" />
                <span className="font-medium truncate max-w-[160px]">{err.file}</span>
                <span className="text-red-600 dark:text-red-500">— {err.error}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status filter pills + toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {/* All button */}
        <button
          className={cn(
            "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
            statusFilter === "all"
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-muted-foreground hover:bg-muted",
          )}
          onClick={() => {
            setStatusFilter("all")
            setPage(1)
          }}
        >
          <span>All</span>
          <span className="font-semibold tabular-nums">{totalDocs}</span>
        </button>

        {/* Status pills */}
        {statusCounts &&
          Object.entries(statusCounts.counts ?? {}).map(([status, count]) => (
            <button
              key={status}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                statusFilter === status
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
              onClick={() => {
                setStatusFilter(statusFilter === status ? "all" : status)
                setPage(1)
              }}
            >
              {status === "PROCESSED" && <CheckCircle2 className="h-3 w-3 text-emerald-500" />}
              {status === "FAILED" && <AlertCircle className="h-3 w-3 text-red-500" />}
              {(status === "PROCESSING" || status === "PARSING" || status === "ANALYZING") && (
                <Loader2 className="h-3 w-3 text-amber-500" />
              )}
              {status === "PENDING" && <Clock className="h-3 w-3 text-slate-400" />}
              <span>{status}</span>
              <span className="font-semibold tabular-nums">{count}</span>
            </button>
          ))}

        <div className="flex-1" />

        {/* Toolbar actions */}
        <Button
          size="sm"
          onClick={() => isModelReady && setUploadDialogOpen(true)}
          disabled={!isModelReady}
        >
          <Upload className="mr-1.5 h-3.5 w-3.5" />
          Upload
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setTextDialogOpen(true)}
          disabled={!isModelReady}
        >
          <FileText className="mr-1 h-3.5 w-3.5" />
          Insert Text
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleReprocess}
          disabled={reprocess.isPending}
          title="Reprocess failed documents"
        >
          <RotateCcw className={cn("h-3.5 w-3.5", reprocess.isPending && "animate-spin")} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleClearCache}
          disabled={clearCacheMutation.isPending}
          title="Clear LLM cache"
        >
          <Eraser className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Document table with drag-drop overlay */}
      <div
        className={cn(
          "relative rounded-lg border flex-1 min-h-0 overflow-auto transition-colors",
          isDragging && "border-primary bg-primary/5",
        )}
        onDragEnter={isModelReady ? handleDragEnter : undefined}
        onDragLeave={isModelReady ? handleDragLeave : undefined}
        onDragOver={isModelReady ? handleDragOver : undefined}
        onDrop={isModelReady ? handleDrop : undefined}
      >
        {/* Drag overlay */}
        {isDragging && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-primary/10 backdrop-blur-sm border-2 border-dashed border-primary">
            <div className="flex flex-col items-center gap-2 text-primary">
              <Upload className="h-8 w-8" />
              <span className="text-sm font-medium">Drop files to upload</span>
            </div>
          </div>
        )}

        <Table>
          <TableHeader className="sticky top-0 bg-surface/95 backdrop-blur-sm z-[1]">
            <TableRow>
              <SortableHeader field="file_path" className="w-[40%]">
                File Name
              </SortableHeader>
              <TableHead className="w-[120px]">Status</TableHead>
              <SortableHeader field="chunks_count" className="w-[80px] text-right">
                Chunks
              </SortableHeader>
              <SortableHeader field="content_length" className="w-[90px] text-right">
                Size
              </SortableHeader>
              <SortableHeader field="created_at" className="w-[150px]">
                Created
              </SortableHeader>
              <TableHead className="w-[60px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {docsLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : documents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                  <div className="flex flex-col items-center gap-2">
                    <FileText className="h-8 w-8 opacity-30" />
                    <span>No documents found</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-medium" title={doc.file_path || doc.id}>
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate max-w-[300px]">
                        {truncatePath(doc.file_path || doc.content_summary || doc.id, 50)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge
                        status={doc.status}
                        onClick={() => setDetailDoc(doc)}
                      />
                      {doc.status === "FAILED" && doc.error_msg && (
                        <AlertCircle
                          className="h-3.5 w-3.5 text-red-500 cursor-pointer hover:text-red-600 shrink-0"
                          onClick={() => setDetailDoc(doc)}
                        />
                      )}
                    </div>
                    {/* Parse progress when parsing */}
                    {doc.status === "PARSING" && (
                      <ParseProgress doc={doc} />
                    )}
                    {/* Per-doc chunk progress when processing */}
                    {doc.status === "PROCESSING" && doc.chunks_count > 0 && (
                      <ChunkProgress doc={doc} />
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {doc.status === "PROCESSING" && doc.chunks_count > 0 ? (
                      <span className="text-primary font-medium">
                        {doc.chunks_count}
                      </span>
                    ) : (
                      doc.chunks_count || "-"
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {doc.content_length > 0
                      ? `${(doc.content_length / 1000).toFixed(1)}k`
                      : "-"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {formatDate(doc.created_at)}
                  </TableCell>
                  <TableCell>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setDeleteConfirmId(doc.id)
                          setDeleteConfirmDoc(doc)
                          setDeleteFile(false)
                          setDeleteLlmCache(false)
                        }}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Page</span>
            <span className="text-sm font-medium tabular-nums">
              {page} / {totalPages}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                setPageSize(Number(v))
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((s) => (
                  <SelectItem key={s} value={String(s)}>
                    {s} / page
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Insert Text Dialog */}
      <Dialog open={textDialogOpen} onOpenChange={setTextDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Insert Text Document</DialogTitle>
            <DialogDescription>
              Paste or type text content to add to this knowledge base.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            placeholder="Enter text content..."
            value={textContent}
            onChange={(e) => setTextContent(e.target.value)}
            className="min-h-[200px]"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setTextDialogOpen(false)
                setTextContent("")
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleInsertText}
              disabled={!textContent.trim() || insertTextMutation.isPending}
            >
              {insertTextMutation.isPending ? "Inserting..." : "Insert"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Document Detail Dialog */}
      <Dialog
        open={detailDoc !== null}
        onOpenChange={(open) => {
          if (!open) setDetailDoc(null)
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Info className="h-4 w-4" />
              Document Details
            </DialogTitle>
            <DialogDescription>
              Detailed information about this document and its processing status.
            </DialogDescription>
          </DialogHeader>

          {detailDoc && (
            <div className="space-y-4">
              <div className="space-y-3">
                <DetailRow
                  label="File"
                  value={
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate font-medium" title={detailDoc.file_path}>
                        {detailDoc.file_path || detailDoc.content_summary || detailDoc.id}
                      </span>
                    </div>
                  }
                />
                <DetailRow
                  label="Status"
                  value={<StatusBadge status={detailDoc.status} />}
                />
                <DetailRow label="ID" value={detailDoc.id} mono />
                {detailDoc.track_id && (
                  <DetailRow label="Track ID" value={detailDoc.track_id} mono />
                )}
              </div>

              {detailDoc.status === "FAILED" && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/30">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
                    <span className="text-sm font-semibold text-red-800 dark:text-red-300">
                      Processing Error
                    </span>
                  </div>
                  {detailDoc.error_msg ? (
                    <pre className="text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap break-words font-mono bg-red-100/50 dark:bg-red-900/20 rounded p-3 leading-relaxed">
                      {detailDoc.error_msg}
                    </pre>
                  ) : (
                    <p className="text-xs text-red-600 dark:text-red-400 italic">
                      No error message was recorded.
                    </p>
                  )}
                  <div className="mt-3 flex items-center gap-2 text-xs text-red-600 dark:text-red-500">
                    <Info className="h-3 w-3" />
                    <span>
                      Error occurred during{" "}
                      <strong>{guessFailureStage(detailDoc)}</strong>
                    </span>
                  </div>
                </div>
              )}

              <div className="rounded-lg border p-3 space-y-2">
                <DetailRow
                  label="Chunks"
                  value={
                    <span className="tabular-nums font-medium">
                      {detailDoc.chunks_count.toLocaleString()}
                    </span>
                  }
                />
                <DetailRow
                  label="Content Length"
                  value={
                    <span className="tabular-nums">
                      {detailDoc.content_length > 0
                        ? `${detailDoc.content_length.toLocaleString()} chars`
                        : "—"}
                    </span>
                  }
                />
                {detailDoc.content_summary && (
                  <DetailRow
                    label="Summary"
                    value={
                      <span className="text-muted-foreground line-clamp-2">
                        {detailDoc.content_summary}
                      </span>
                    }
                  />
                )}
              </div>

              {/* Processing progress — shown when actively processing or completed with metadata */}
              {detailDoc.status === "PROCESSING" &&
                detailDoc.chunks_count > 0 && (
                  <ProcessingProgressCard doc={detailDoc} />
                )}

              <div className="rounded-lg border p-3 space-y-2">
                <DetailRow
                  label="Created"
                  value={formatDate(detailDoc.created_at)}
                />
                <DetailRow
                  label="Updated"
                  value={formatDate(detailDoc.updated_at)}
                />
                {/* Processing duration for completed docs */}
                {detailDoc.status === "PROCESSED" &&
                  typeof detailDoc.metadata?.processing_start_time === "number" &&
                  typeof detailDoc.metadata?.processing_end_time === "number" && (
                    <DetailRow
                      label="Duration"
                      value={
                        <span className="tabular-nums">
                          {formatDuration(
                            (detailDoc.metadata.processing_end_time as number) -
                              (detailDoc.metadata.processing_start_time as number)
                          )}
                        </span>
                      }
                    />
                  )}
              </div>

              {detailDoc.metadata && Object.keys(detailDoc.metadata).length > 0 && (
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground mb-2">Metadata</div>
                  <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap break-words bg-muted rounded p-2 max-h-[120px] overflow-auto">
                    {JSON.stringify(detailDoc.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailDoc(null)}>
              Close
            </Button>
            {detailDoc?.status === "FAILED" && (
              <Button
                variant="default"
                onClick={() => {
                  handleReprocess()
                  setDetailDoc(null)
                }}
                disabled={reprocess.isPending}
              >
                <RotateCcw className={cn("mr-1.5 h-3.5 w-3.5", reprocess.isPending && "animate-spin")} />
                Reprocess
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Processing Document Delete Warning Dialog */}
      <Dialog
        open={processingDeleteDoc !== null}
        onOpenChange={(open) => {
          if (!open) setProcessingDeleteDoc(null)
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-5 w-5" />
              文档正在处理中
            </DialogTitle>
            <DialogDescription className="pt-2">
              该文档正在进行{" "}
              <span className="font-semibold text-foreground">
                {processingDeleteDoc?.status === "PARSING" && "文件解析"}
                {processingDeleteDoc?.status === "ANALYZING" && "内容分析"}
                {processingDeleteDoc?.status === "PREPROCESSED" && "预处理"}
                {processingDeleteDoc?.status === "PROCESSING" && "实体抽取"}
              </span>
              ，强制删除可能导致数据不一致。
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium">
                {processingDeleteDoc?.file_path || processingDeleteDoc?.content_summary || processingDeleteDoc?.id}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <StatusBadge status={processingDeleteDoc?.status ?? "PENDING"} />
              {processingDeleteDoc?.chunks_count ? (
                <span className="tabular-nums">
                  {typeof processingDeleteDoc.metadata?.chunks_processed === "number"
                    ? `${processingDeleteDoc.metadata.chunks_processed}/`
                    : ""}
                  {processingDeleteDoc.chunks_count} chunks
                </span>
              ) : null}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={() => setProcessingDeleteDoc(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleForceDelete}
              disabled={cancelPipeline.isPending || deleteDocs.isPending}
            >
              {(cancelPipeline.isPending || deleteDocs.isPending) ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  {cancelPipeline.isPending ? "正在终止..." : "正在删除..."}
                </>
              ) : (
                <>
                  <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                  强制终止并删除
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upload Dialog */}
      <UploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        knowledgeName={knowledgeName}
      />

      {/* Delete Confirm Dialog */}
      <Dialog
        open={deleteConfirmId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteConfirmId(null)
            setDeleteConfirmDoc(null)
            setDeleteFile(false)
            setDeleteLlmCache(false)
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-4 w-4" />
              删除文档
            </DialogTitle>
            <DialogDescription className="pt-1">
              确认要删除该文档吗？以下是本次操作的清理范围说明。
            </DialogDescription>
          </DialogHeader>

          {/* 文件信息 */}
          {deleteConfirmDoc && (
            <div className="rounded-lg border bg-muted/40 px-3 py-2.5 flex items-center gap-2.5">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span
                className="text-sm font-medium truncate"
                title={deleteConfirmDoc.file_path || deleteConfirmDoc.id}
              >
                {deleteConfirmDoc.file_path || deleteConfirmDoc.content_summary || deleteConfirmDoc.id}
              </span>
            </div>
          )}

          {/* 删除范围说明 */}
          <div className="space-y-3 rounded-lg border p-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              本次删除范围
            </p>

            {/* 始终执行 */}
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-500" />
              <div>
                <p className="text-sm font-medium">移除文档索引记录</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  从知识库状态表中删除此文档的追踪记录（始终执行）
                </p>
              </div>
            </div>

            {/* delete_file — 可选，已实现 */}
            <label className="flex items-start gap-2.5 cursor-pointer group">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-border accent-primary cursor-pointer shrink-0"
                checked={deleteFile}
                onChange={(e) => setDeleteFile(e.target.checked)}
              />
              <div>
                <p className="text-sm font-medium group-hover:text-foreground transition-colors">
                  同时删除原始上传文件
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  删除 uploads/ 目录的源文件及 Docling 解析产物（.docling_raw）
                </p>
              </div>
            </label>

            {/* delete_llm_cache — 后端暂未实现，展示为禁用 */}
            <div className="flex items-start gap-2.5 opacity-50 select-none">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-border cursor-not-allowed shrink-0"
                disabled
                checked={false}
                readOnly
              />
              <div>
                <p className="text-sm font-medium flex items-center gap-1.5">
                  清除 LLM 抽取缓存
                  <span className="text-[10px] font-normal rounded px-1.5 py-0.5 bg-muted text-muted-foreground border">
                    暂未实现
                  </span>
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  实体/关系抽取的 LLM 缓存清除，后续版本支持
                </p>
              </div>
            </div>

            {/* 分隔线 + 向量/图数据说明 */}
            <div className="border-t pt-2.5">
              <div className="flex items-start gap-2 text-xs text-muted-foreground">
                <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                <span>
                  向量数据库（chunk embeddings）和知识图谱（实体/关系）
                  <span className="font-medium text-foreground/70">不会</span>
                  被清除，如需完整重建请在设置中重置索引。
                </span>
              </div>
            </div>
          </div>

          {/* 警告：仅勾选"删除文件"时出现 */}
          {deleteFile && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-950/30">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500 mt-0.5" />
              <p className="text-xs text-amber-700 dark:text-amber-400">
                源文件删除后<span className="font-semibold">无法恢复</span>，如需重新索引该文档须重新上传。
              </p>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setDeleteConfirmId(null)
                setDeleteConfirmDoc(null)
                setDeleteFile(false)
                setDeleteLlmCache(false)
              }}
              disabled={deleteDocs.isPending}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteConfirmId && handleDeleteDoc(deleteConfirmId, deleteConfirmDoc ?? undefined)}
              disabled={deleteDocs.isPending}
            >
              {deleteDocs.isPending ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  删除中…
                </>
              ) : (
                <>
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                  确认删除
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/* ── Helper components ────────────────────────────────────────────────────── */

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <span className="w-24 shrink-0 text-muted-foreground font-medium">{label}</span>
      <span className={cn("flex-1 min-w-0 break-all", mono && "font-mono text-xs")}>
        {value}
      </span>
    </div>
  )
}

/**
 * Per-document chunk processing progress indicator.
 * Shows a mini progress bar with "X/Y chunks" text.
 */
/**
 * Parse progress indicator — shows elapsed time and file size during PARSING.
 */
function ParseProgress({ doc }: { doc: DocStatusInfo }) {
  const startTime =
    typeof doc.metadata?.parse_start_time === "number"
      ? (doc.metadata.parse_start_time as number)
      : null
  const fileSize =
    typeof doc.metadata?.file_size === "number"
      ? (doc.metadata.file_size as number)
      : doc.content_length || 0

  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!startTime) return
    const update = () => setElapsed(Math.max(0, Date.now() / 1000 - startTime))
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [startTime])

  const sizeLabel = fileSize > 1024 * 1024
    ? `${(fileSize / 1024 / 1024).toFixed(1)}MB`
    : fileSize > 1024
      ? `${(fileSize / 1024).toFixed(0)}KB`
      : fileSize > 0
        ? `${fileSize}B`
        : ""

  return (
    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin text-amber-500 shrink-0" />
      <span className="tabular-nums">{Math.round(elapsed)}s</span>
      {sizeLabel && <span>· {sizeLabel}</span>}
    </div>
  )
}

/**
 * Per-document chunk processing progress indicator.
 * Shows a mini progress bar with "X/Y chunks" text.
 */
function ChunkProgress({ doc }: { doc: DocStatusInfo }) {
  const total = doc.chunks_count || 0
  const processed =
    typeof doc.metadata?.chunks_processed === "number"
      ? (doc.metadata.chunks_processed as number)
      : 0

  if (total <= 0) return null

  const pct = Math.min(100, Math.round((processed / Math.max(1, total)) * 100))

  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 min-w-[48px] rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] tabular-nums text-muted-foreground whitespace-nowrap">
        {processed}/{total}
      </span>
    </div>
  )
}

/**
 * Processing progress card for the detail dialog.
 * Shows chunk progress bar, elapsed time, and estimated time remaining.
 */
function ProcessingProgressCard({ doc }: { doc: DocStatusInfo }) {
  const total = doc.chunks_count || 0
  const processed =
    typeof doc.metadata?.chunks_processed === "number"
      ? (doc.metadata.chunks_processed as number)
      : 0
  const startTime =
    typeof doc.metadata?.processing_start_time === "number"
      ? (doc.metadata.processing_start_time as number)
      : null

  const pct = Math.min(100, Math.round((processed / Math.max(1, total)) * 100))

  // Elapsed time
  const elapsed = startTime ? (Date.now() / 1000 - startTime) : null

  // Estimate remaining time based on progress
  const remaining =
    elapsed && processed > 0
      ? (elapsed / processed) * (total - processed)
      : null

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          Extracting entities
        </span>
        <span className="tabular-nums text-primary font-medium">
          {processed}/{total} chunks
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-primary/15 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{pct}% complete</span>
        {elapsed != null && (
          <span>
            Elapsed: {formatDuration(elapsed)}
            {remaining != null && remaining > 0 && (
              <> · ETA: {formatDuration(remaining)}</>
            )}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Format a duration in seconds to a human-readable string.
 */
function formatDuration(seconds: number): string {
  if (seconds < 0) return "—"
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  const hours = Math.floor(mins / 60)
  const remainMins = mins % 60
  return remainMins > 0 ? `${hours}h ${remainMins}m` : `${hours}h`
}

/**
 * Best-effort guess of which pipeline stage failed, based on the document's
 * last known status and error message.
 */
function guessFailureStage(doc: DocStatusInfo): string {
  const err = (doc.error_msg ?? "").toLowerCase()

  if (err.includes("llm not configured") || err.includes("chat model")) {
    return "model binding (Chat Model not bound)"
  }
  if (err.includes("embedding model not configured") || err.includes("embedding model not bound")) {
    return "model binding (Embedding Model not bound)"
  }
  if (err.includes("upload") || err.includes("network") || err.includes("http")) {
    return "upload"
  }
  if (err.includes("parse") || err.includes("extract") || err.includes("empty document")) {
    return "parsing"
  }
  if (err.includes("chunk") || err.includes("split")) {
    return "chunking"
  }
  if (err.includes("embed") || err.includes("vector") || err.includes("embedding")) {
    return "embedding"
  }
  if (err.includes("entity") || err.includes("relation") || err.includes("llm") || err.includes("model")) {
    return "entity extraction (LLM)"
  }
  if (err.includes("cancel")) {
    return "pipeline (cancelled)"
  }
  if (err.includes("graph") || err.includes("merge")) {
    return "graph merge"
  }
  if (err.includes("storage") || err.includes("write") || err.includes("persist")) {
    return "storage"
  }

  return "processing"
}
