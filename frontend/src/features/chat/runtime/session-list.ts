import type { SessionMeta } from "@/stores/chat-store"

export function mergeSessionList(sessions: SessionMeta[], session: SessionMeta): SessionMeta[] {
  return [session, ...sessions.filter((item) => item.id !== session.id)].sort(
    (a, b) => b.updated_at - a.updated_at,
  )
}

export function mergeSessionLists(current: SessionMeta[], incoming: SessionMeta[]): SessionMeta[] {
  const byId = new Map<string, SessionMeta>()
  for (const session of current) {
    byId.set(session.id, session)
  }
  for (const session of incoming) {
    const existing = byId.get(session.id)
    byId.set(
      session.id,
      !existing || session.updated_at >= existing.updated_at ? session : existing,
    )
  }
  return Array.from(byId.values()).sort((a, b) => b.updated_at - a.updated_at)
}
