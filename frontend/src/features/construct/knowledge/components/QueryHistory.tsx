import { useCallback, useState } from "react"
import {
  Clock,
  Trash2,
  RotateCcw,
  Search,
  ChevronDown,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { HistoryEntry } from "../hooks/useQueryHistory"

interface QueryHistoryProps {
  entries: HistoryEntry[]
  onSelect: (entry: HistoryEntry) => void
  onRemove: (id: string) => void
  onClearAll: () => void
  className?: string
}

function formatTimestamp(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return "Just now"
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return d.toLocaleDateString()
}

const MODE_COLORS: Record<string, string> = {
  local: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  global: "bg-green-500/10 text-green-600 dark:text-green-400",
  hybrid: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  naive: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  mix: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
  bypass: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
}

export function QueryHistory({
  entries,
  onSelect,
  onRemove,
  onClearAll,
  className,
}: QueryHistoryProps) {
  const [search, setSearch] = useState("")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filteredEntries = entries.filter(
    (e) =>
      e.query.toLowerCase().includes(search.toLowerCase()) ||
      e.mode.toLowerCase().includes(search.toLowerCase()),
  )

  const toggleExpanded = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }, [])

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Clock className="h-8 w-8 text-muted-foreground/30 mb-2" />
        <p className="text-sm text-muted-foreground">No query history</p>
      </div>
    )
  }

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-medium flex-1">
          Query History ({entries.length})
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs text-muted-foreground hover:text-destructive"
          onClick={onClearAll}
        >
          <Trash2 className="mr-1 h-3 w-3" />
          Clear
        </Button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search history..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-7 pl-7 text-xs"
          />
        </div>
      </div>

      {/* Entries */}
      <div className="flex-1 overflow-y-auto">
        {filteredEntries.length === 0 ? (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No matching entries
          </p>
        ) : (
          filteredEntries.map((entry) => (
            <div
              key={entry.id}
              className="group border-b border-border/50 last:border-b-0"
            >
              <button
                className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/50 transition-colors"
                onClick={() => toggleExpanded(entry.id)}
              >
                <div className="mt-0.5 shrink-0">
                  {expandedId === entry.id ? (
                    <ChevronDown className="h-3 w-3 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-3 w-3 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{entry.query}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className={cn(
                        "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium",
                        MODE_COLORS[entry.mode] || "bg-muted text-muted-foreground",
                      )}
                    >
                      {entry.mode}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                    {entry.referenceCount > 0 && (
                      <span className="text-[10px] text-muted-foreground">
                        {entry.referenceCount} refs
                      </span>
                    )}
                  </div>
                </div>
              </button>

              {expandedId === entry.id && (
                <div className="px-3 pb-2 pl-8 space-y-2">
                  {entry.response && (
                    <p className="text-xs text-muted-foreground line-clamp-3">
                      {entry.response.slice(0, 200)}
                      {entry.response.length > 200 ? "..." : ""}
                    </p>
                  )}
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 text-xs"
                      onClick={() => onSelect(entry)}
                    >
                      <RotateCcw className="mr-1 h-3 w-3" />
                      Re-query
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-muted-foreground hover:text-destructive"
                      onClick={() => onRemove(entry.id)}
                    >
                      <Trash2 className="mr-1 h-3 w-3" />
                      Remove
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
