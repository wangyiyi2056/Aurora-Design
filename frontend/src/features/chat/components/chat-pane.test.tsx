import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ChatPane } from "./chat-pane"
import type { ChatMessage } from "../types"

function renderPane(messages: ChatMessage[]) {
  return render(
    <ChatPane
      messages={messages}
      streaming={false}
      error={null}
      projectId="session-1"
      projectFiles={[]}
      onEnsureProject={async () => "session-1"}
      onSend={vi.fn()}
      onStop={vi.fn()}
      conversations={[]}
      activeConversationId="session-1"
      onSelectConversation={vi.fn()}
      onDeleteConversation={vi.fn()}
    />,
  )
}

describe("ChatPane message actions", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it("fills the composer when editing a user message", () => {
    renderPane([{ id: "u1", role: "user", content: "重试这个请求" }])

    fireEvent.click(screen.getByRole("button", { name: "编辑" }))

    expect(screen.getByRole("textbox")).toHaveValue("重试这个请求")
  })

  it("copies a user message", () => {
    renderPane([{ id: "u1", role: "user", content: "复制这段内容" }])

    fireEvent.click(screen.getByRole("button", { name: "复制" }))

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("复制这段内容")
  })

  it("allows clicking a failed user turn to edit it again", () => {
    renderPane([
      { id: "u1", role: "user", content: "会失败的请求" },
      { id: "a1", role: "assistant", content: "", runStatus: "failed" },
    ])

    fireEvent.click(screen.getByTestId("retry-edit-user-message-u1"))

    expect(screen.getByRole("textbox")).toHaveValue("会失败的请求")
  })

  it("opens a user attachment with its workspace path instead of only the basename", () => {
    const onRequestOpenFile = vi.fn()
    render(
      <ChatPane
        messages={[
          {
            id: "u1",
            role: "user",
            content: "看这张图",
            attachments: [
              {
                path: "uploads/logo.png",
                name: "logo.png",
                kind: "image",
                url: "/api/v1/workspaces/session-1/raw/uploads/logo.png",
              },
            ],
          },
        ]}
        streaming={false}
        error={null}
        projectId="session-1"
        projectFiles={[]}
        projectFileNames={new Set(["uploads/logo.png", "logo.png"])}
        onRequestOpenFile={onRequestOpenFile}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        conversations={[]}
        activeConversationId="session-1"
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /logo\.png/ }))

    expect(onRequestOpenFile).toHaveBeenCalledWith("uploads/logo.png")
  })
})
