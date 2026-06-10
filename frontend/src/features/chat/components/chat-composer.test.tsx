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

  it("renders the selected design skill inside the input area", () => {
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
            examplePrompt: "",
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
        selectedDesignSkillId="dashboard"
        onSelectDesignSkill={vi.fn()}
      />,
    )

    const chip = screen.getByTestId("composer-selected-design-skill")

    expect(chip).toHaveTextContent("dashboard")
    expect(chip.closest(".composer-input-wrap")).not.toBeNull()
  })

  it("selects and clears a design system", () => {
    const onSelectDesignSystem = vi.fn()
    const designSystems = [
      {
        id: "vercel",
        title: "Vercel",
        category: "Developer Tools",
        summary: "Black and white precision.",
        swatches: ["#ffffff", "#171717"],
        surface: "web",
        source: "built-in",
        status: "published",
        isEditable: false,
        enabled: true,
      },
    ]

    const { rerender } = render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        designSystems={designSystems}
        selectedDesignSystemId={null}
        onSelectDesignSystem={onSelectDesignSystem}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /import/i }))
    fireEvent.click(screen.getByRole("menuitem", { name: /design system library/i }))
    fireEvent.click(screen.getByRole("button", { name: "Use Vercel" }))

    expect(onSelectDesignSystem).toHaveBeenCalledWith("vercel")

    rerender(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={vi.fn()}
        onStop={vi.fn()}
        designSystems={designSystems}
        selectedDesignSystemId="vercel"
        onSelectDesignSystem={onSelectDesignSystem}
      />,
    )

    expect(screen.getByTestId("composer-selected-design-system")).toHaveTextContent("Vercel")
    fireEvent.click(screen.getByRole("button", { name: "Clear design system Vercel" }))
    expect(onSelectDesignSystem).toHaveBeenCalledWith(null)
  })

  it("selects a custom prompt from @ mentions and sends its id", () => {
    const onSend = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={onSend}
        onStop={vi.fn()}
        customPrompts={[
          {
            id: "prompt-1",
            name: "sales-dashboard",
            category: "general",
            template: "Use dense dashboard patterns.",
            variables: [],
            version: 1,
            enabled: true,
            description: "Dashboard guidance",
            extra: { prompt_type: "custom" },
            created_at: 1,
            updated_at: 1,
          },
        ]}
      />,
    )

    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "@sales", selectionStart: 6 },
    })
    fireEvent.click(screen.getByRole("button", { name: /sales-dashboard/i }))

    expect(screen.getByTestId("composer-selected-custom-prompt")).toHaveTextContent("sales-dashboard")

    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "@sales-dashboard Build the page", selectionStart: 31 },
    })
    fireEvent.click(screen.getByTestId("chat-send"))

    expect(onSend).toHaveBeenCalledWith(
      "@sales-dashboard Build the page",
      [],
      [],
      ["prompt-1"],
      [{ kind: "custom_prompt", id: "prompt-1", name: "sales-dashboard" }],
    )
  })

  it("removes a selected custom prompt before sending", () => {
    const onSend = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={onSend}
        onStop={vi.fn()}
        customPrompts={[
          {
            id: "prompt-1",
            name: "sales-dashboard",
            category: "general",
            template: "Use dense dashboard patterns.",
            variables: [],
            version: 1,
            enabled: true,
            description: "Dashboard guidance",
            extra: { prompt_type: "custom" },
            created_at: 1,
            updated_at: 1,
          },
        ]}
      />,
    )

    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "@sales", selectionStart: 6 },
    })
    fireEvent.click(screen.getByRole("button", { name: /sales-dashboard/i }))
    fireEvent.click(screen.getByRole("button", { name: "Remove prompt sales-dashboard" }))
    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "Build the page", selectionStart: 14 },
    })
    fireEvent.click(screen.getByTestId("chat-send"))

    expect(screen.queryByTestId("composer-selected-custom-prompt")).not.toBeInTheDocument()
    expect(onSend).toHaveBeenCalledWith("Build the page", [], [], [], [])
  })


  it("sends and clears selected datasource context", () => {
    const onSend = vi.fn()
    const onSelectDatasource = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={onSend}
        onStop={vi.fn()}
        datasources={[{ name: "sales-db", db_type: "sqlite", description: "Sales", connected: true }]}
        selectedDatasourceName="sales-db"
        onSelectDatasource={onSelectDatasource}
      />,
    )

    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "介绍这个数据源", selectionStart: 7 },
    })
    fireEvent.click(screen.getByTestId("chat-send"))

    expect(onSend).toHaveBeenCalledWith(
      "介绍这个数据源",
      [],
      [],
      [],
      [{ kind: "datasource", name: "sales-db" }],
    )
    expect(onSelectDatasource).toHaveBeenCalledWith(null)
  })

  it("sends and clears selected design contexts", () => {
    const onSend = vi.fn()
    const onSelectDesignSkill = vi.fn()
    const onSelectDesignSystem = vi.fn()

    render(
      <ChatComposer
        projectId="session-1"
        projectFiles={[]}
        streaming={false}
        onEnsureProject={async () => "session-1"}
        onSend={onSend}
        onStop={vi.fn()}
        designSkills={[
          {
            id: "dashboard",
            name: "dashboard",
            description: "Build dashboards.",
            source: "builtin",
            mode: "template",
            surface: "web",
            scenario: "dashboard",
            previewType: "html",
            examplePrompt: "",
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
        selectedDesignSkillId="dashboard"
        onSelectDesignSkill={onSelectDesignSkill}
        designSystems={[
          {
            id: "vercel",
            title: "Vercel",
            category: "Developer Tools",
            summary: "Black and white precision.",
            swatches: ["#ffffff", "#171717"],
            surface: "web",
            source: "built-in",
            status: "published",
            isEditable: false,
            enabled: true,
          },
        ]}
        selectedDesignSystemId="vercel"
        onSelectDesignSystem={onSelectDesignSystem}
      />,
    )

    fireEvent.change(screen.getByTestId("chat-composer-input"), {
      target: { value: "Build UI", selectionStart: 8 },
    })
    fireEvent.click(screen.getByTestId("chat-send"))

    expect(onSend).toHaveBeenCalledWith(
      "Build UI",
      [],
      [],
      [],
      [
        { kind: "design_skill", id: "dashboard", name: "dashboard" },
        { kind: "design_system", id: "vercel", title: "Vercel" },
      ],
    )
    expect(onSelectDesignSkill).toHaveBeenCalledWith(null)
    expect(onSelectDesignSystem).toHaveBeenCalledWith(null)
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
