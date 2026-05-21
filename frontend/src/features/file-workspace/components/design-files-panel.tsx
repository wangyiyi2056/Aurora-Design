import { File, FileCode2, FileImage, FileText, Pencil, Plus, RefreshCw, Trash2, Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { WorkspaceFile, WorkspaceFileKind } from "../types"

interface DesignFilesPanelProps {
  files: WorkspaceFile[]
  activeName: string | null
  onOpenFile: (name: string) => void
  onRefresh?: () => void
  onCreate?: () => void
  onUpload?: () => void
  onRename?: (name: string) => void
  onDelete?: (name: string) => void
}

export function DesignFilesPanel({
  files,
  activeName,
  onOpenFile,
  onRefresh,
  onCreate,
  onUpload,
  onRename,
  onDelete,
}: DesignFilesPanelProps) {
  const sorted = [...files].sort((a, b) => b.mtime - a.mtime || a.name.localeCompare(b.name))
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 shrink-0 items-center justify-between border-b px-4">
        <div>
          <div className="text-sm font-semibold">Files</div>
          <div className="text-xs text-muted-foreground">{files.length} items</div>
        </div>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="New file" onClick={onCreate}>
            <Plus className="h-4 w-4" />
          </Button>
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Upload" onClick={onUpload}>
            <Upload className="h-4 w-4" />
          </Button>
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Refresh" onClick={onRefresh}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-2">
        {sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
            No files yet
          </div>
        ) : (
          <div className="space-y-1">
            {sorted.map((file) => (
              <div
                key={file.name}
                className={cn(
                  "group flex items-center gap-2 rounded-md border border-transparent px-2 py-2",
                  activeName === file.name ? "bg-muted" : "hover:bg-muted/50",
                )}
              >
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  onClick={() => onOpenFile(file.name)}
                  aria-label={`Open ${file.name}`}
                >
                  <KindIcon kind={file.kind} />
                  <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{file.kind}</span>
                </button>
                {onRename ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 opacity-0 group-hover:opacity-100"
                    aria-label="Rename file"
                    title={`Rename ${file.name}`}
                    onClick={() => onRename(file.name)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                ) : null}
                {onDelete ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 opacity-0 group-hover:opacity-100"
                    aria-label="Delete file"
                    title={`Delete ${file.name}`}
                    onClick={() => onDelete(file.name)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function KindIcon({ kind }: { kind: WorkspaceFileKind }) {
  if (kind === "html" || kind === "code" || kind === "json") {
    return <FileCode2 className="h-4 w-4 shrink-0 text-blue-500" />
  }
  if (kind === "image") return <FileImage className="h-4 w-4 shrink-0 text-emerald-500" />
  if (kind === "markdown" || kind === "text") return <FileText className="h-4 w-4 shrink-0 text-amber-500" />
  return <File className="h-4 w-4 shrink-0 text-muted-foreground" />
}
