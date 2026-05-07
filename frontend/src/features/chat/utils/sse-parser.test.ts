import { describe, expect, it } from "vitest"

import { ChatSSEState, parseSSEChunk } from "./sse-parser"
import { parseTodoWriteInput } from "../runtime/todos"

describe("ChatSSEState", () => {
  it("exposes streaming text before text_end without duplicating the final part", () => {
    const state = new ChatSSEState()

    state.processEvent({ type: "text_start" })
    state.processEvent({ type: "text_delta", content: "hello" })

    expect(state.toMessageParts()).toMatchObject([
      { type: "text", text: "hello" },
    ])

    state.processEvent({ type: "text_delta", content: " world" })

    expect(state.toMessageParts()).toMatchObject([
      { type: "text", text: "hello world" },
    ])

    state.processEvent({ type: "text_end", finish_reason: "stop" })

    expect(state.toMessageParts()).toMatchObject([
      { type: "text", text: "hello world" },
    ])
  })

  it("updates tool results by event id when tool calls are interleaved", () => {
    const state = new ChatSSEState()

    state.processEvent({
      type: "tool_call_start",
      id: "tool-a",
      tool_name: "Read",
      arguments: "{\"file\":\"a.csv\"}",
    })
    state.processEvent({
      type: "tool_call_start",
      id: "tool-b",
      tool_name: "Bash",
      arguments: "{\"cmd\":\"pwd\"}",
    })
    state.processEvent({
      type: "tool_call_result",
      id: "tool-a",
      tool_name: "Read",
      content: "a-result",
    })

    expect(state.toMessageParts()).toMatchObject([
      {
        id: "tool-a",
        type: "tool",
        state: { status: "completed", output: "a-result" },
      },
      {
        id: "tool-b",
        type: "tool",
        state: { status: "running" },
      },
    ])
  })
})

describe("parseSSEChunk", () => {
  it("accepts compact data: lines without a space after the colon", () => {
    expect(parseSSEChunk('data:{"type":"text_delta","content":"ok"}')).toEqual([
      { type: "text_delta", content: "ok" },
    ])
  })
})

describe("parseTodoWriteInput", () => {
  it("normalizes TodoWrite tool input into visible unfinished tasks", () => {
    expect(
      parseTodoWriteInput({
        todos: [
          { content: "读取数据", status: "completed" },
          { content: "生成图表", status: "in_progress", activeForm: "选择图表" },
          { content: "写摘要" },
          { content: "" },
        ],
      })
    ).toEqual([
      { content: "读取数据", status: "completed", activeForm: undefined },
      { content: "生成图表", status: "in_progress", activeForm: "选择图表" },
      { content: "写摘要", status: "pending", activeForm: undefined },
    ])
  })
})
