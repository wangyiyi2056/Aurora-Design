import { useEffect, useMemo, useRef, useState } from "react"
import { FileText, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { deleteWorkspaceFile, renameWorkspaceFile, uploadWorkspaceFiles, writeWorkspaceTextFile } from "../services/workspace-files"
import { useWorkspaceTabsStore } from "../state/workspace-tabs-store"
import type { WorkspaceFile, WorkspaceTabsState } from "../types"
import { DesignFilesPanel } from "./design-files-panel"
import { FileViewer } from "./file-viewer"

interface FileWorkspaceProps {
  workspaceId: string
  files: WorkspaceFile[]
  loading?: boolean
  onRefreshFiles?: () => Promise<void> | void
  openRequest?: { name: string; nonce: number } | null
}

const FILES_TAB = "__files__"

export function FileWorkspace({
  workspaceId,
  files,
  loading = false,
  onRefreshFiles,
  openRequest,
}: FileWorkspaceProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const { getTabsState, setTabsState } = useWorkspaceTabsStore()
  const persisted = getTabsState(workspaceId)
  const [localState, setLocalState] = useState<WorkspaceTabsState>(persisted)
  const [dragActive, setDragActive] = useState(false)
  const [selectedNames, setSelectedNames] = useState<Set<string>>(() => new Set())
  const active = localState.active ?? FILES_TAB

  useEffect(() => {
    setLocalState(getTabsState(workspaceId))
    setSelectedNames(new Set())
  }, [getTabsState, workspaceId])

  useEffect(() => {
    const names = new Set(files.map((file) => file.name))
    setSelectedNames((current) => new Set([...current].filter((name) => names.has(name))))
  }, [files])

  useEffect(() => {
    if (!openRequest?.name) return
    openFile(openRequest.name)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRequest?.nonce])

  function commit(next: WorkspaceTabsState) {
    setLocalState(next)
    setTabsState(workspaceId, next)
  }

  function openFile(name: string) {
    const tabs = localState.tabs.includes(name) ? localState.tabs : [...localState.tabs, name]
    commit({ tabs, active: name })
  }

  function closeFile(name: string) {
    const tabs = localState.tabs.filter((tab) => tab !== name)
    const nextActive = active === name ? tabs.at(-1) ?? FILES_TAB : active
    commit({ tabs, active: nextActive === FILES_TAB ? null : nextActive })
  }

  async function handleUpload(filesToUpload: FileList | null) {
    const picked = Array.from(filesToUpload ?? [])
    if (picked.length === 0) return
    const result = await uploadWorkspaceFiles(workspaceId, picked)
    await onRefreshFiles?.()
    const html = result.files.find((file) => file.kind === "html")
    if (html) openFile(html.name)
  }

  async function handleRename(name: string) {
    const nextName = window.prompt("Rename file", name)?.trim()
    if (!nextName || nextName === name) return
    const renamed = await renameWorkspaceFile(workspaceId, name, nextName)
    const tabs = localState.tabs.map((tab) => (tab === name ? renamed.file.name : tab))
    const nextActive = active === name ? renamed.file.name : active
    commit({ tabs, active: nextActive === FILES_TAB ? null : nextActive })
    await onRefreshFiles?.()
  }

  async function handleCreate() {
    const name = window.prompt("New file name", "generated/index.html")?.trim()
    if (!name) return
    const content = window.prompt("Initial content", initialContentFor(name))
    if (content == null) return
    const file = await writeWorkspaceTextFile(workspaceId, name, content, { overwrite: false })
    await onRefreshFiles?.()
    if (file) openFile(file.name)
  }

  async function handleDelete(name: string) {
    const ok = await deleteWorkspaceFile(workspaceId, name)
    if (!ok) return
    setSelectedNames((current) => {
      const next = new Set(current)
      next.delete(name)
      return next
    })
    closeFile(name)
    await onRefreshFiles?.()
  }

  function toggleSelected(name: string) {
    setSelectedNames((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  async function handleDeleteSelected() {
    const names = [...selectedNames]
    if (names.length === 0) return
    const results = await Promise.all(names.map((name) => deleteWorkspaceFile(workspaceId, name)))
    const deleted = new Set(names.filter((_, index) => results[index]))
    if (deleted.size > 0) {
      const tabs = localState.tabs.filter((tab) => !deleted.has(tab))
      const nextActive = deleted.has(active) ? tabs.at(-1) ?? FILES_TAB : active
      commit({ tabs, active: nextActive === FILES_TAB ? null : nextActive })
      setSelectedNames((current) => new Set([...current].filter((name) => !deleted.has(name))))
      await onRefreshFiles?.()
    }
  }

  const fileByName = useMemo(() => new Map(files.map((file) => [file.name, file])), [files])
  const activeFile = active === FILES_TAB ? null : fileByName.get(active) ?? null
  const visibleTabs = localState.tabs.filter((name) => fileByName.has(name))

  return (
    <section
      className={cn(
        "relative flex h-full min-h-[520px] min-w-0 overflow-hidden rounded-lg border bg-background",
        dragActive && "ring-2 ring-primary",
      )}
      onDragEnter={(event) => {
        event.preventDefault()
        setDragActive(true)
      }}
      onDragOver={(event) => {
        event.preventDefault()
        setDragActive(true)
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setDragActive(false)
        }
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragActive(false)
        void handleUpload(event.dataTransfer.files)
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(event) => {
          void handleUpload(event.target.files)
          event.currentTarget.value = ""
        }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-11 shrink-0 items-center gap-1 overflow-x-auto border-b px-2">
          <TabButton active={active === FILES_TAB} onClick={() => commit({ ...localState, active: null })}>
            <FileText className="h-4 w-4" />
            Files
          </TabButton>
          {visibleTabs.map((name) => {
            const file = fileByName.get(name)
            return (
              <TabButton key={name} active={active === name} onClick={() => commit({ ...localState, active: name })}>
                <span className="max-w-[180px] truncate">{basename(name)}</span>
                <span className="text-[10px] text-muted-foreground">{file?.kind}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  aria-label={`Close ${name}`}
                  onClick={(event) => {
                    event.stopPropagation()
                    closeFile(name)
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </TabButton>
            )
          })}
          {loading ? <span className="ml-auto text-xs text-muted-foreground">Loading...</span> : null}
        </div>
        <div className="min-h-0 flex-1">
          {activeFile ? <FileViewer workspaceId={workspaceId} file={activeFile} /> : null}
          {!activeFile && (
            <div className="h-full">
              <DesignFilesPanel
                files={files}
                activeName={null}
                onOpenFile={openFile}
                onRefresh={onRefreshFiles}
                onCreate={handleCreate}
                onUpload={() => inputRef.current?.click()}
                onRename={handleRename}
                onDelete={handleDelete}
                selectedNames={selectedNames}
                onToggleSelected={toggleSelected}
                onDeleteSelected={handleDeleteSelected}
              />
            </div>
          )}
        </div>
      </div>
      {dragActive ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-background/70 backdrop-blur-[1px]">
          <div className="rounded-md border bg-background px-4 py-2 text-sm font-medium shadow-sm">Drop files to upload</div>
        </div>
      ) : null}
    </section>
  )
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-2 rounded-md px-3 text-sm transition-colors",
        active ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function basename(path: string): string {
  return path.split("/").filter(Boolean).at(-1) ?? path
}

function initialContentFor(path: string): string {
  const lower = path.toLowerCase()
  if (lower.endsWith(".html")) return "<!doctype html>\n<html>\n<body>\n  <h1>Hello Aurora</h1>\n</body>\n</html>\n"
  if (lower.endsWith(".md")) return "# Notes\n"
  if (lower.endsWith(".json")) return "{}\n"
  return ""
}
