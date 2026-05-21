import { describe, expect, it } from "vitest"

import { deriveFileOps } from "./file-ops"
import type { AgentEvent } from "@/features/chat/types"

describe("deriveFileOps", () => {
  it("groups read write edit tool events by full path with worst status", () => {
    const events: AgentEvent[] = [
      { kind: "tool_use", id: "1", name: "Read", input: { file_path: "reports/index.html" } },
      { kind: "tool_result", toolUseId: "1", content: "ok", isError: false },
      { kind: "tool_use", id: "2", name: "Edit", input: { path: "reports/index.html" } },
      { kind: "tool_use", id: "3", name: "Write", input: { file_path: "assets/logo.png" } },
      { kind: "tool_result", toolUseId: "3", content: "nope", isError: true },
    ]

    expect(deriveFileOps(events)).toEqual([
      {
        path: "index.html",
        fullPath: "reports/index.html",
        ops: ["read", "edit"],
        opCounts: { read: 1, write: 0, edit: 1 },
        total: 2,
        status: "running",
      },
      {
        path: "logo.png",
        fullPath: "assets/logo.png",
        ops: ["write"],
        opCounts: { read: 0, write: 1, edit: 0 },
        total: 1,
        status: "error",
      },
    ])
  })
})
