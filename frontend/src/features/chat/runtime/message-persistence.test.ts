import { describe, expect, it } from "vitest"

import { eventsFromMessage, resolvedMessageText, textFromEvents } from "./message-persistence"
import type { ChatMessage } from "@/stores/chat-store"

describe("message persistence helpers", () => {
  it("rebuilds assistant text from legacy text events when content is empty", () => {
    expect(
      resolvedMessageText({
        content: "",
        events: [
          { kind: "thinking", text: "skip" },
          { kind: "text", text: "hello " },
          { kind: "text", text: "world" },
        ],
      }),
    ).toBe("hello world")
  })

  it("turns streaming message parts into persistable events", () => {
    const message: ChatMessage = {
      role: "assistant",
      content: [
        { id: "text-1", type: "text", text: "Answer" },
        { id: "reason-1", type: "reasoning", text: "Thinking" },
        {
          id: "tool-1",
          type: "tool",
          tool: "write_file",
          state: { status: "completed", input: { path: "index.html" }, output: "ok" },
        },
      ],
    }

    expect(textFromEvents(eventsFromMessage(message))).toBe("Answer")
    expect(eventsFromMessage(message)).toContainEqual({
      kind: "tool_result",
      toolUseId: "tool-1",
      content: "ok",
      isError: false,
    })
  })
})
