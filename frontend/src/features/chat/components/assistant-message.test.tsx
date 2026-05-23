import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AssistantMessage } from "./assistant-message"
import type { ChatMessage } from "../types"

describe("AssistantMessage", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it("shows streamed thinking content expanded while the assistant is running", () => {
    const message: ChatMessage = {
      id: "assistant-1",
      role: "assistant",
      content: "",
      events: [{ kind: "thinking", text: "reading project structure" }],
      createdAt: 1,
      startedAt: 1,
    }

    const { container } = render(
      <AssistantMessage
        message={message}
        streaming
        projectId={null}
      />
    )

    expect(screen.getByText("Thinking")).toBeVisible()
    expect(container.querySelector(".thinking-body")).toHaveTextContent(
      "reading project structure"
    )
  })

  it("updates the expanded thinking body as new reasoning text streams in", () => {
    const baseMessage: ChatMessage = {
      id: "assistant-1",
      role: "assistant",
      content: "",
      events: [{ kind: "thinking", text: "reading" }],
      createdAt: 1,
      startedAt: 1,
    }

    const { container, rerender } = render(
      <AssistantMessage
        message={baseMessage}
        streaming
        projectId={null}
      />
    )

    expect(container.querySelector(".thinking-body")).toHaveTextContent("reading")

    rerender(
      <AssistantMessage
        message={{
          ...baseMessage,
          events: [{ kind: "thinking", text: "reading project structure" }],
        }}
        streaming
        projectId={null}
      />
    )

    expect(container.querySelector(".thinking-body")).toHaveTextContent(
      "reading project structure"
    )
  })

  it("copies assistant text content", async () => {
    render(
      <AssistantMessage
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "这里是回复内容",
        }}
        streaming={false}
        projectId={null}
      />,
    )

    screen.getByRole("button", { name: "复制" }).click()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("这里是回复内容")
  })
})
