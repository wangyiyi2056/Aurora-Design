import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { describe, expect, it } from "vitest"

import { AgentProcessView } from "./agent-process-view"
import type { ChatMessage } from "../types"

describe("AgentProcessView", () => {
  it("collapses previous rounds and expands the latest round by default", () => {
    const messages: ChatMessage[] = [
      { id: "u1", role: "user", content: "第一轮" },
      { id: "a1", role: "assistant", content: "第一轮完成", endTime: 1000 },
      { id: "u2", role: "user", content: "第二轮" },
      { id: "a2", role: "assistant", content: "第二轮完成", endTime: 2000 },
    ]

    render(<AgentProcessView messages={messages} streaming={false} />)

    expect(screen.getByTestId("agent-process-run-0")).not.toHaveAttribute("open")
    expect(screen.getByTestId("agent-process-run-1")).toHaveAttribute("open")
  })
})
