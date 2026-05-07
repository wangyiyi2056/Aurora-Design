export type TodoStatus = "pending" | "in_progress" | "completed"

export interface TodoItem {
  content: string
  status: TodoStatus
  activeForm?: string
}

export function parseTodoWriteInput(input: unknown): TodoItem[] {
  if (!input || typeof input !== "object") return []
  const todos = (input as { todos?: unknown }).todos
  if (!Array.isArray(todos)) return []

  return todos
    .map((todo): TodoItem | null => {
      if (!todo || typeof todo !== "object") return null
      const record = todo as Record<string, unknown>
      const content = typeof record.content === "string" ? record.content.trim() : ""
      if (!content) return null
      const status =
        record.status === "completed" || record.status === "in_progress"
          ? record.status
          : "pending"

      return {
        content,
        status,
        activeForm:
          typeof record.activeForm === "string" ? record.activeForm : undefined,
      }
    })
    .filter((todo): todo is TodoItem => todo !== null)
}

export function unfinishedTodosFromToolInput(input: unknown): TodoItem[] {
  return parseTodoWriteInput(input).filter((todo) => todo.status !== "completed")
}
