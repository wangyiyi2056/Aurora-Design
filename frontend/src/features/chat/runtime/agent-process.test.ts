import { describe, expect, it } from "vitest"

import { buildAgentProcessModel } from "./agent-process"
import type { ChatMessage } from "../types"

describe("agent process model", () => {
  it("groups multiple turns and pairs tool use with tool result", () => {
    const messages: ChatMessage[] = [
      { id: "u1", role: "user", content: "生成登录页" },
      {
        id: "a1",
        role: "assistant",
        content: "完成",
        endTime: 1000,
        events: [
          { kind: "status", label: "Planning" },
          { kind: "tool_use", id: "tool-1", name: "Write", input: { file_path: "login.html" } },
          { kind: "tool_result", toolUseId: "tool-1", content: "ok", isError: false },
          { kind: "usage", inputTokens: 10, outputTokens: 20, durationMs: 1200 },
        ],
      },
      { id: "u2", role: "user", content: "再改一下" },
      { id: "a2", role: "assistant", content: "已修改", endTime: 2000 },
    ]

    const model = buildAgentProcessModel(messages)

    expect(model.groups).toHaveLength(2)
    expect(model.groups[0]?.nodes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: "tool", status: "completed", fileName: "login.html" }),
        expect.objectContaining({ kind: "usage", detail: "输入 10 · 输出 20 · 1s" }),
      ]),
    )
    expect(model.groups[1]?.title).toBe("再改一下")
  })

  it("marks the latest unpaired tool call as active while streaming", () => {
    const messages: ChatMessage[] = [
      { id: "u1", role: "user", content: "查文件" },
      {
        id: "a1",
        role: "assistant",
        content: "",
        events: [{ kind: "tool_use", id: "tool-1", name: "Read", input: { path: "src/app.tsx" } }],
      },
    ]

    const model = buildAgentProcessModel(messages, { streaming: true })
    const tool = model.groups[0]?.nodes.find((node) => node.kind === "tool")

    expect(model.phase).toBe("tool")
    expect(model.statusLabel).toBe("正在使用 Read")
    expect(tool).toMatchObject({ active: true, status: "running", fileName: "app.tsx" })
  })

  it("falls back to text events when assistant content is empty", () => {
    const model = buildAgentProcessModel([
      { id: "u1", role: "user", content: "总结" },
      {
        id: "a1",
        role: "assistant",
        content: "",
        endTime: 1000,
        events: [
          { kind: "thinking", text: "整理上下文" },
          { kind: "text", text: "这是" },
          { kind: "text", text: "结论" },
        ],
      },
    ])

    expect(model.groups[0]?.nodes).toContainEqual(
      expect.objectContaining({ kind: "final", content: "这是结论" }),
    )
  })

  it("surfaces artifact events as clickable file nodes when a title includes a filename", () => {
    const model = buildAgentProcessModel([
      { id: "u1", role: "user", content: "生成页面" },
      {
        id: "a1",
        role: "assistant",
        content: "完成",
        endTime: 1000,
        events: [
          {
            kind: "live_artifact",
            action: "created",
            projectId: "p1",
            artifactId: "art1",
            title: "index.html",
          },
        ],
      },
    ])

    expect(model.groups[0]?.nodes).toContainEqual(
      expect.objectContaining({ kind: "artifact", fileName: "index.html", status: "completed" }),
    )
  })
})
