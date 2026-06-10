import { useCallback, useEffect, useRef, useState } from "react"
import {
  Upload,
  FileText,
  X,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  CloudUpload,
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { useUploadDocument } from "../hooks/use-knowledge-v2"

/* ── Types ──────────────────────────────────────────────────────────────────── */

type FileUploadStatus = "uploading" | "success" | "error"

interface FileEntry {
  id: string
  file: File
  status: FileUploadStatus
  error?: string
}

interface UploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  knowledgeName: string
}

/* ── Helpers ─────────────────────────────────────────────────────────────────── */

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === "object" && err !== null && "message" in err)
    return String((err as { message: unknown }).message)
  return "上传失败，请重试"
}

/* ── Component ───────────────────────────────────────────────────────────────── */

export function UploadDialog({ open, onOpenChange, knowledgeName }: UploadDialogProps) {
  const { t } = useTranslation("construct")
  const [isDragging, setIsDragging] = useState(false)
  const [fileEntries, setFileEntries] = useState<FileEntry[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  // 用 ref 存 mutate，避免 closure 问题
  const uploadDoc = useUploadDocument()
  const uploadDocRef = useRef(uploadDoc)
  uploadDocRef.current = uploadDoc

  /* ── 弹框关闭时重置 ── */
  const reset = useCallback(() => {
    setFileEntries([])
    setIsDragging(false)
  }, [])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      // 正在上传中，不允许关闭
      if (!nextOpen && fileEntries.some((f) => f.status === "uploading")) return
      if (!nextOpen) reset()
      onOpenChange(nextOpen)
    },
    [fileEntries, onOpenChange, reset],
  )

  /* ── 弹框关闭时清理 ── */
  useEffect(() => {
    if (!open) reset()
  }, [open, reset])

  /* ── 全部成功 → 延迟自动关闭 ── */
  useEffect(() => {
    if (fileEntries.length === 0) return
    const allDone = fileEntries.every((f) => f.status === "success" || f.status === "error")
    const hasError = fileEntries.some((f) => f.status === "error")
    if (allDone && !hasError) {
      const timer = setTimeout(() => {
        onOpenChange(false)
        reset()
      }, 900)
      return () => clearTimeout(timer)
    }
  }, [fileEntries, onOpenChange, reset])

  /* ── 上传单个文件（加入即触发）── */
  const uploadFile = useCallback(
    (entry: FileEntry) => {
      uploadDocRef.current.mutate(
        { name: knowledgeName, file: entry.file },
        {
          onSuccess: () => {
            setFileEntries((prev) =>
              prev.map((f) => (f.id === entry.id ? { ...f, status: "success" } : f)),
            )
          },
          onError: (err) => {
            setFileEntries((prev) =>
              prev.map((f) =>
                f.id === entry.id
                  ? { ...f, status: "error", error: extractErrorMessage(err) }
                  : f,
              ),
            )
          },
        },
      )
    },
    [knowledgeName],
  )

  /* ── 添加文件 → 立即开始上传 ── */
  const addAndUpload = useCallback(
    (files: File[]) => {
      if (files.length === 0) return
      // 过滤同名（以当前正在处理的为准）
      setFileEntries((prev) => {
        const existingNames = new Set(prev.map((f) => f.file.name))
        const newEntries: FileEntry[] = files
          .filter((f) => !existingNames.has(f.name))
          .map((file) => ({
            id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
            file,
            status: "uploading",
          }))
        // 在同一 setState 批次中把新条目加入，然后立即触发上传
        setTimeout(() => {
          newEntries.forEach(uploadFile)
        }, 0)
        return [...prev, ...newEntries]
      })
    },
    [uploadFile],
  )

  /* ── 失败重试 ── */
  const retryFile = useCallback(
    (id: string) => {
      setFileEntries((prev) => {
        const entry = prev.find((f) => f.id === id)
        if (!entry) return prev
        const updated = prev.map((f) =>
          f.id === id ? { ...f, status: "uploading" as FileUploadStatus, error: undefined } : f,
        )
        setTimeout(() => uploadFile({ ...entry, status: "uploading" }), 0)
        return updated
      })
    },
    [uploadFile],
  )

  /* ── 移除（仅 error 时可手动移除）── */
  const removeFile = useCallback((id: string) => {
    setFileEntries((prev) => prev.filter((f) => f.id !== id))
  }, [])

  /* ── Drag handlers ── */

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)
      addAndUpload(Array.from(e.dataTransfer.files))
    },
    [addAndUpload],
  )

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      addAndUpload(Array.from(e.target.files ?? []))
      if (fileInputRef.current) fileInputRef.current.value = ""
    },
    [addAndUpload],
  )

  /* ── Derived state ── */

  const uploadingCount = fileEntries.filter((f) => f.status === "uploading").length
  const successCount = fileEntries.filter((f) => f.status === "success").length
  const errorCount = fileEntries.filter((f) => f.status === "error").length
  const isUploading = uploadingCount > 0
  const allDone = fileEntries.length > 0 && !isUploading
  const allSuccess = allDone && errorCount === 0

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CloudUpload className="h-5 w-5 text-primary" />
            {t("knowledge.v2.doc.uploadDoc")}
          </DialogTitle>
          <DialogDescription>
            {t("knowledge.v2.doc.uploadDesc")}
          </DialogDescription>
        </DialogHeader>

        {/* 拖拽 / 选择区域 */}
        <div
          className={cn(
            "relative rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer select-none",
            isDragging
              ? "border-primary bg-primary/8 scale-[1.005]"
              : "border-border hover:border-primary/50 hover:bg-muted/40",
            fileEntries.length > 0 ? "py-4" : "py-12",
          )}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
          />

          {fileEntries.length === 0 ? (
            /* 空状态 */
            <div className="flex flex-col items-center gap-3 text-muted-foreground pointer-events-none">
              <div
                className={cn(
                  "rounded-full p-4 transition-colors",
                  isDragging ? "bg-primary/15 text-primary" : "bg-muted",
                )}
              >
                <Upload className="h-7 w-7" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">
                  {isDragging ? t("knowledge.v2.doc.releaseToUpload") : t("knowledge.v2.doc.dragFilesHere")}
                </p>
                <p className="text-xs mt-0.5 text-muted-foreground">
                  {t("knowledge.v2.doc.clickOrDragHint")}
                </p>
              </div>
            </div>
          ) : (
            /* 文件列表 */
            <div
              className="px-3 space-y-1.5 max-h-60 overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {fileEntries.map((entry) => (
                <FileRow
                  key={entry.id}
                  entry={entry}
                  onRemove={removeFile}
                  onRetry={retryFile}
                />
              ))}
              {/* 继续添加提示 */}
              <p className="pt-1 text-center text-xs text-muted-foreground pointer-events-none">
                {isUploading
                  ? `${t("knowledge.v2.doc.uploading")} ${successCount + errorCount}/${fileEntries.length}…`
                  : t("knowledge.v2.doc.continueAdd")}
              </p>
            </div>
          )}
        </div>

        {/* 汇总 Banner（仅全部完成后显示） */}
        {allDone && (
          <div
            className={cn(
              "flex items-center gap-2.5 rounded-lg border px-4 py-3 text-sm font-medium",
              allSuccess
                ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-400"
                : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-400",
            )}
          >
            {allSuccess ? (
              <>
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>
                  {successCount} {t("knowledge.v2.doc.uploadSuccessClose")}
                </span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <div className="flex-1">
                  {successCount > 0 && (
                    <span className="mr-2">{successCount} {t("knowledge.v2.doc.uploadSuccessText")}</span>
                  )}
                  <span>{errorCount} {t("knowledge.v2.doc.uploadFailedRetry")}</span>
                </div>
              </>
            )}
          </div>
        )}

        {/* 底部操作栏（只有出错时才需要关闭按钮，成功时自动关闭） */}
        {allDone && !allSuccess && (
          <div className="flex justify-end">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              {t("common.close")}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

/* ── FileRow ─────────────────────────────────────────────────────────────────── */

function FileRow({
  entry,
  onRemove,
  onRetry,
}: {
  entry: FileEntry
  onRemove: (id: string) => void
  onRetry: (id: string) => void
}) {
  const { t } = useTranslation("construct")
  const { id, file, status, error } = entry

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors",
        status === "success" &&
          "border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-950/20",
        status === "error" &&
          "border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/20",
        status === "uploading" && "border-primary/30 bg-primary/5",
      )}
    >
      {/* 状态图标 */}
      <div className="shrink-0">
        {status === "uploading" && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
        {status === "success" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
        {status === "error" && <AlertTriangle className="h-4 w-4 text-red-500" />}
      </div>

      {/* 文件名 + 大小 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span
            className="truncate font-medium text-foreground"
            style={{ maxWidth: 240 }}
            title={file.name}
          >
            {file.name}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {formatFileSize(file.size)}
          </span>
        </div>
        {status === "uploading" && (
          <p className="text-[11px] text-primary/60 mt-0.5">{t("knowledge.v2.doc.uploading")}…</p>
        )}
        {status === "success" && (
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-0.5">
            {t("knowledge.v2.doc.submittedProcessing")}
          </p>
        )}
        {status === "error" && error && (
          <p className="text-[11px] text-red-600 dark:text-red-400 mt-0.5 line-clamp-1">
            {error}
          </p>
        )}
      </div>

      {/* 操作按钮 */}
      {status === "error" && (
        <div className="flex items-center gap-1 shrink-0">
          <button
            className="rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/10 transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              onRetry(id)
            }}
            title={t("knowledge.v2.doc.retry")}
          >
            {t("knowledge.v2.doc.retry")}
          </button>
          <button
            className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              onRemove(id)
            }}
            title={t("knowledge.v2.doc.remove")}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* 上传中 icon placeholder，防止布局跳动 */}
      {status === "uploading" && <div className="w-[50px] shrink-0" />}

      {/* 成功后展示小图标 */}
      {status === "success" && (
        <FileText className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
      )}
    </div>
  )
}
