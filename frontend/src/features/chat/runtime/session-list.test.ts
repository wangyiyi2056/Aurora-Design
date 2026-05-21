import { describe, expect, it } from "vitest"

import { mergeSessionList, mergeSessionLists } from "./session-list"

describe("mergeSessionList", () => {
  it("inserts a newly saved session immediately and keeps newest first", () => {
    const merged = mergeSessionList(
      [
        { id: "old", title: "Old", created_at: 1, updated_at: 10, message_count: 2 },
      ],
      { id: "new", title: "New prompt", created_at: 2, updated_at: 20, message_count: 1 },
    )

    expect(merged.map((session) => session.id)).toEqual(["new", "old"])
  })

  it("replaces an existing session instead of duplicating it", () => {
    const merged = mergeSessionList(
      [
        { id: "same", title: "Draft", created_at: 1, updated_at: 10, message_count: 1 },
        { id: "old", title: "Old", created_at: 1, updated_at: 9, message_count: 1 },
      ],
      { id: "same", title: "Final", created_at: 1, updated_at: 30, message_count: 2 },
    )

    expect(merged).toHaveLength(2)
    expect(merged[0]).toMatchObject({ id: "same", title: "Final", message_count: 2 })
  })

  it("preserves optimistic sessions when a stale query result arrives", () => {
    const merged = mergeSessionLists(
      [
        { id: "optimistic", title: "Just sent", created_at: 2, updated_at: 30, message_count: 1 },
      ],
      [
        { id: "older", title: "Older", created_at: 1, updated_at: 10, message_count: 2 },
      ],
    )

    expect(merged.map((session) => session.id)).toEqual(["optimistic", "older"])
  })
})
