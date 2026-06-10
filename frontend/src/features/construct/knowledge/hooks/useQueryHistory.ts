import { useCallback, useState, useEffect } from "react"

export interface HistoryEntry {
  id: string
  query: string
  mode: string
  response: string
  timestamp: number
  referenceCount: number
}

const STORAGE_KEY = "aurora_query_history"
const MAX_ENTRIES = 100

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveHistory(entries: HistoryEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Storage full or unavailable — silently ignore
  }
}

export function useQueryHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(loadHistory)

  useEffect(() => {
    saveHistory(entries)
  }, [entries])

  const addEntry = useCallback(
    (entry: Omit<HistoryEntry, "id" | "timestamp">) => {
      const newEntry: HistoryEntry = {
        ...entry,
        id: `qh-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        timestamp: Date.now(),
      }
      setEntries((prev) => {
        const next = [newEntry, ...prev]
        return next.slice(0, MAX_ENTRIES)
      })
      return newEntry
    },
    [],
  )

  const removeEntry = useCallback((id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }, [])

  const clearAll = useCallback(() => {
    setEntries([])
  }, [])

  const updateEntry = useCallback(
    (id: string, updates: Partial<Pick<HistoryEntry, "response" | "referenceCount">>) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...updates } : e)),
      )
    },
    [],
  )

  return { entries, addEntry, removeEntry, clearAll, updateEntry }
}
