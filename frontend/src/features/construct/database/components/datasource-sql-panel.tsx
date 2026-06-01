import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Bookmark, Pencil, Play, Save, Trash2 } from "lucide-react"
import { toast } from "sonner"
import {
  useRunQuery,
  useSavedQueries,
  useSaveQuery,
  useUpdateSavedQuery,
  useDeleteSavedQuery,
} from "../hooks/use-datasources"
import type { SavedQuery } from "@/services/database"

interface DatasourceSqlPanelProps {
  name: string
}

const SELECT_SAVE_ACTION = "__save_new__"

export function DatasourceSqlPanel({ name }: DatasourceSqlPanelProps) {
  const [sql, setSql] = useState("")
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [saveDescription, setSaveDescription] = useState("")
  const [selectedValue, setSelectedValue] = useState("")
  const [editingQuery, setEditingQuery] = useState<SavedQuery | null>(null)

  const query = useRunQuery()
  const savedQueries = useSavedQueries(name)
  const saveMutation = useSaveQuery()
  const updateMutation = useUpdateSavedQuery()
  const deleteMutation = useDeleteSavedQuery()

  const savedList = savedQueries.data?.items ?? []
  const saveDialogInputRef = useRef<HTMLInputElement>(null)

  const isEditing = editingQuery !== null

  const handleRun = useCallback(() => {
    if (!sql.trim()) return
    query.mutate({ name, sql: sql.trim() })
  }, [sql, name, query])

  // Auto-focus description input when save dialog opens
  useEffect(() => {
    if (saveDialogOpen) {
      const timer = setTimeout(() => saveDialogInputRef.current?.focus(), 100)
      return () => clearTimeout(timer)
    }
  }, [saveDialogOpen])

  const openEditDialog = (e: React.MouseEvent, q: SavedQuery) => {
    e.stopPropagation()
    setEditingQuery(q)
    setSaveDescription(q.description)
    setSql(q.sql)
    setSaveDialogOpen(true)
    setSelectedValue("")
  }

  const openSaveDialog = () => {
    setEditingQuery(null)
    setSaveDescription("")
    setSaveDialogOpen(true)
  }

  const closeDialog = () => {
    setSaveDialogOpen(false)
    setEditingQuery(null)
    setSaveDescription("")
  }

  const handleSelectChange = (value: string) => {
    if (value === SELECT_SAVE_ACTION) {
      openSaveDialog()
      setSelectedValue("")
      return
    }

    const found = savedList.find((q) => q.id === value)
    if (found) {
      setSql(found.sql)
      setSelectedValue(value)
      query.mutate({ name, sql: found.sql.trim() })
    }
  }

  const handleSave = () => {
    const trimmedSql = sql.trim()
    const trimmedDesc = saveDescription.trim()
    if (!trimmedSql) {
      toast.error("No SQL to save")
      return
    }
    if (!trimmedDesc) {
      toast.error("Please enter a description")
      return
    }

    if (isEditing && editingQuery) {
      updateMutation.mutate(
        { queryId: editingQuery.id, data: { sql: trimmedSql, description: trimmedDesc } },
        {
          onSuccess: () => {
            toast.success("Query updated")
            closeDialog()
          },
          onError: () => {
            toast.error("Failed to update query")
          },
        }
      )
      return
    }

    saveMutation.mutate(
      { datasource_name: name, sql: trimmedSql, description: trimmedDesc },
      {
        onSuccess: () => {
          toast.success("Query saved")
          closeDialog()
        },
        onError: () => {
          toast.error("Failed to save query")
        },
      }
    )
  }

  const handleDelete = (e: React.MouseEvent, queryItem: SavedQuery) => {
    e.stopPropagation()
    deleteMutation.mutate(queryItem.id, {
      onSuccess: () => {
        toast.success("Query deleted")
        if (selectedValue === queryItem.id) {
          setSelectedValue("")
        }
      },
      onError: () => {
        toast.error("Failed to delete query")
      },
    })
  }

  const isMutating = saveMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-3">
      {/* Saved queries dropdown */}
      <Select value={selectedValue} onValueChange={handleSelectChange}>
        <SelectTrigger className="w-full h-9 text-sm">
          <Bookmark className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
          <SelectValue placeholder="Select a saved query..." />
        </SelectTrigger>
        <SelectContent>
          {savedList.length > 0 ? (
            savedList.map((q) => (
              <SelectItem key={q.id} value={q.id}>
                <div className="flex items-center justify-between w-full gap-2 pr-1">
                  <div className="flex-1 min-w-0">
                    <span className="truncate block text-sm">{q.description}</span>
                    <span className="text-[10px] text-muted-foreground truncate block font-mono">
                      {q.sql.length > 60 ? q.sql.slice(0, 60) + "..." : q.sql}
                    </span>
                  </div>
                  <div className="flex items-center shrink-0 gap-0.5">
                    <button
                      type="button"
                      className="p-1 rounded hover:bg-accent/50 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={(e) => openEditDialog(e, q)}
                      title="Edit query"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      onClick={(e) => handleDelete(e, q)}
                      title="Delete query"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </SelectItem>
            ))
          ) : (
            <div className="px-2 py-1.5 text-xs text-muted-foreground">
              No saved queries yet
            </div>
          )}
          {sql.trim() && (
            <>
              <div className="my-1 mx-2 h-px bg-border" />
              <SelectItem value={SELECT_SAVE_ACTION}>
                <div className="flex items-center gap-2 text-primary">
                  <Save className="h-3.5 w-3.5" />
                  <span className="text-sm">Save current query...</span>
                </div>
              </SelectItem>
            </>
          )}
        </SelectContent>
      </Select>

      {/* SQL textarea */}
      <Textarea
        placeholder="SELECT * FROM ..."
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        className="font-mono text-sm resize-y"
        style={{ minHeight: "300px" }}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault()
            handleRun()
          }
        }}
      />

      {/* Action bar */}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleRun} disabled={query.isPending || !sql.trim()}>
          <Play className="mr-1.5 h-3.5 w-3.5" />
          {query.isPending ? "Running..." : "Run SQL"}
        </Button>
        {selectedValue ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              const current = savedList.find((q) => q.id === selectedValue)
              if (current) openEditDialog({ stopPropagation: () => {} } as React.MouseEvent, current)
            }}
            disabled={!sql.trim() || isMutating}
          >
            <Pencil className="mr-1.5 h-3.5 w-3.5" />
            Update
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            onClick={openSaveDialog}
            disabled={!sql.trim() || isMutating}
          >
            <Save className="mr-1.5 h-3.5 w-3.5" />
            Save
          </Button>
        )}
        <span className="text-xs text-muted-foreground">Ctrl+Enter to execute</span>
      </div>

      {/* Results */}
      {query.data && (
        <div className="rounded-md border bg-muted/50 p-3 max-h-[300px] overflow-auto">
          {query.data.success ? (
            <pre className="text-xs font-mono whitespace-pre-wrap break-words">
              {typeof query.data.result === "string"
                ? query.data.result
                : JSON.stringify(query.data.result, null, 2)}
            </pre>
          ) : (
            <p className="text-xs text-destructive">{query.data.error}</p>
          )}
        </div>
      )}

      {/* Save / Update dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={(open) => { if (!open) closeDialog() }}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{isEditing ? "Update SQL Query" : "Save SQL Query"}</DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Modify the description for this saved query."
                : "Give this query a description so you can find it later."}
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 space-y-3">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Description</label>
              <Input
                ref={saveDialogInputRef}
                placeholder="e.g. Monthly revenue by category"
                value={saveDescription}
                onChange={(e) => setSaveDescription(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    handleSave()
                  }
                }}
              />
            </div>
            {isEditing && (
              <div>
                <label className="text-sm font-medium mb-1.5 block">SQL</label>
                <Textarea
                  value={sql}
                  onChange={(e) => setSql(e.target.value)}
                  className="font-mono text-xs resize-y"
                  style={{ minHeight: "120px" }}
                />
              </div>
            )}
            {!isEditing && sql.trim() && (
              <div className="rounded-md bg-muted/50 p-2 max-h-32 overflow-auto">
                <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-words">
                  {sql.trim()}
                </pre>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isMutating || !saveDescription.trim()}>
              {isMutating
                ? (isEditing ? "Updating..." : "Saving...")
                : (isEditing ? "Update" : "Save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
