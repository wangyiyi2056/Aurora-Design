import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ChatComposer } from "./chat-composer"
import { uploadProjectFiles } from "../providers/registry"

vi.mock("../providers/registry", () => ({
  projectRawUrl: (path: string) => `/raw/${path}`,
  openFolderDialog: vi.fn(),
  uploadProjectFiles: vi.fn(),
}))

describe("ChatComposer attachments", () => {
  beforeEach(() => {
    vi.mocked(uploadProjectFiles).mockReset()
  })

  it("opens a staged uploaded attachment in the workspace preview", async () => {
    vi.mocked(uploadProjectFiles).mockResolvedValue({
      uploaded: [
        {
          path: "uploads/logo.png",
          name: "logo.png",
          kind: "image",
          url: "/api/v1/workspaces/session-1/raw/uploads/logo.png",
          size: 12,
        },
      ],
      failed: [],
    })
    const onRequestOpenFile = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        onRequestOpenFile={onRequestOpenFile}
      />,
    )

    const input = screen.getByTestId("chat-file-input")
    const file = new File(["fake"], "logo.png", { type: "image/png" })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Open logo.png" })).toBeVisible()
    })

    fireEvent.click(screen.getByRole("button", { name: "Open logo.png" }))

    expect(onRequestOpenFile).toHaveBeenCalledWith("uploads/logo.png")
  })

  it("shows the current provider and model beside import", () => {
    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        modelDisplayName="CLI-Claude Code"
      />,
    )

    expect(screen.getByTitle("Current model: CLI-Claude Code")).toBeVisible()
  })

  it("selects a design skill and can insert its example prompt", () => {
    const onSelectDesignSkill = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        designSkills={[
          {
            id: "dashboard",
            name: "dashboard",
            description: "Build dense operational dashboards.",
            source: "builtin",
            mode: "template",
            surface: "web",
            scenario: "dashboard",
            previewType: "html",
            examplePrompt: "Create a sales dashboard",
            hasAssets: false,
            hasReferences: false,
            triggers: [],
            body: null,
            hidden: false,
            status: "ready",
            adapterKind: "",
            dependencyType: "",
            requiredTools: [],
          },
        ]}
        selectedDesignSkillId={null}
        onSelectDesignSkill={onSelectDesignSkill}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /import/i }))
    fireEvent.click(screen.getByRole("menuitem", { name: /skills/i }))
    fireEvent.click(screen.getByRole("button", { name: "Use dashboard" }))

    expect(onSelectDesignSkill).toHaveBeenCalledWith("dashboard")

    fireEvent.click(screen.getByRole("button", { name: /import/i }))
    fireEvent.click(screen.getByRole("menuitem", { name: /skills/i }))
    fireEvent.click(screen.getByRole("button", { name: "Use prompt from dashboard" }))

    expect(screen.getByTestId("chat-composer-input")).toHaveValue("Create a sales dashboard")
  })

  it("shows design skill loading in the picker", () => {
    const { rerender } = render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        designSkills={[]}
        designSkillsLoading
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /import/i }))
    fireEvent.click(screen.getByRole("menuitem", { name: /skills/i }))

    expect(screen.getByText("Loading design skills...")).toBeVisible()

    rerender(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        designSkills={[]}
        designSkillsError="Design skill catalog unavailable"
      />,
    )

    expect(screen.getByText("Design skill catalog unavailable")).toBeVisible()
  })
})
