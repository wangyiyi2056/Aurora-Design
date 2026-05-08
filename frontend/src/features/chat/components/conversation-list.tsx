import { useCallback, useEffect } from "react"
import { MessageSquare, Plus, Trash2 } from "lucide-react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useChatStore } from "@/stores/chat-store"
import { listSessions, loadSession, deleteSession } from "@/services/chat"
import { toast } from "sonner"

function formatRelativeTime(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp * 1000
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return "yesterday"
  if (days < 7) return `${days}d ago`

  const d = new Date(timestamp * 1000)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-muted/30 animate-pulse"
          style={{ width: `${60 + Math.random() * 40}%` }}
        />
      ))}
    </div>
  )
}

export function ConversationList({
  activeId,
  collapsed,
  onSelect,
  onDelete,
  onNewChat,
}: ConversationListProps) {
  const setSessions = useChatStore((s) => s.setSessions)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
    refetchOnMount: true,
  })

  const sessions = data?.sessions ?? []

  useEffect(() => {
    if (sessions.length > 0) {
      setSessions(sessions)
    }
  }, [sessions, setSessions])

  const handleSelect = useCallback(
    async (sessionId: string) => {
      if (sessionId === activeId) return
      try {
        const res = await loadSession(sessionId)
        const messages = res.messages
          .filter(
            (m) => m.type === "user" || m.type === "assistant"
          )
          .map((m) => ({
            role:
              m.role === "user" || m.type === "user"
                ? ("user" as const)
                : ("assistant" as const),
            content: m.content,
            events: m.events ?? [],
            attachments: m.attachments ?? [],
            startTime: m.timestamp ? toMillis(m.timestamp) : undefined,
            endTime: m.type === "assistant" && m.timestamp ? toMillis(m.timestamp) : undefined,
          }))
        useChatStore.getState().loadSessionMessages(messages)
        useChatStore.getState().setSessionId(sessionId)
        onSelect?.(sessionId)
        toast.success("Conversation loaded")
      } catch {
        toast.error("Failed to load conversation")
      }
    },
    [activeId, onSelect]
  )

  const handleDelete = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(sessionId)
        // Remove from local state
        const updated = sessions.filter((s) => s.id !== sessionId)
        setSessions(updated)
        queryClient.setQueryData(["sessions"], { sessions: updated })

        // If deleting the active session, reset
        if (sessionId === activeId) {
          useChatStore.getState().resetToNewChat()
        }
        onDelete?.(sessionId)
        toast.success("Conversation deleted")
      } catch {
        toast.error("Failed to delete conversation")
      }
    },
    [sessions, activeId, setSessions, queryClient, onDelete]
  )

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 py-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="New Chat"
        >
          <Plus className="h-4 w-4" />
        </button>
        {isLoading ? (
          <div className="flex flex-col gap-1.5 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
            <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
            <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
          </div>
        ) : sessions.length === 0 ? null : (
          <div className="flex flex-col gap-1.5 py-1">
            {sessions.slice(0, 8).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => handleSelect(s.id)}
                className={`h-1.5 w-1.5 rounded-full transition-colors ${
                  s.id === activeId
                    ? "bg-primary"
                    : "bg-muted-foreground/30 hover:bg-muted-foreground/50"
                }`}
                title={s.title}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        onClick={onNewChat}
        className="flex items-center gap-2 rounded px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors w-full"
      >
        <Plus className="h-4 w-4" />
        <span>New Chat</span>
      </button>

      <div className="px-3 py-1.5 mt-1">
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/50">
          Conversations
        </span>
      </div>

      {isLoading ? (
        <Skeleton lines={4} />
      ) : sessions.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-3 py-8 text-muted-foreground/40">
          <MessageSquare className="h-6 w-6" />
          <span className="text-xs">No conversations yet</span>
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          {sessions.slice(0, 30).map((s) => (
            <div key={s.id} className="group relative">
              <button
                type="button"
                onClick={() => handleSelect(s.id)}
                className={`flex items-center gap-2 w-full rounded px-3 py-1.5 text-left text-sm transition-colors ${
                  s.id === activeId
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate flex-1">{s.title}</span>
                <span className="text-[10px] text-muted-foreground/40 shrink-0">
                  {formatRelativeTime(s.updated_at)}
                </span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(s.id)
                }}
                className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6 flex items-center justify-center rounded text-muted-foreground/30 hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                title="Delete conversation"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function toMillis(timestamp: number): number {
  return timestamp < 10_000_000_000 ? timestamp * 1000 : timestamp
}

interface ConversationListProps {
  activeId: string | null
  collapsed: boolean
  onSelect?: (id: string) => void
  onDelete?: (id: string) => void
  onNewChat: () => void
}
