import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import DesignSystemsPage from "./design-systems-page"
import {
  createDesignSystem,
  deleteDesignSystem,
  getDesignSystem,
  listDesignSystems,
  toggleDesignSystem,
  updateDesignSystem,
} from "@/services/design-systems"

vi.mock("@/features/construct/components/construct-shell", () => ({
  ConstructShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/services/design-systems", async () => {
  const actual = await vi.importActual<typeof import("@/services/design-systems")>("@/services/design-systems")
  return {
    ...actual,
    createDesignSystem: vi.fn(),
    deleteDesignSystem: vi.fn(),
    getDesignSystem: vi.fn(),
    listDesignSystems: vi.fn(),
    toggleDesignSystem: vi.fn(),
    updateDesignSystem: vi.fn(),
  }
})

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <DesignSystemsPage />
    </QueryClientProvider>,
  )
}

describe("DesignSystemsPage", () => {
  beforeEach(() => {
    vi.mocked(listDesignSystems).mockResolvedValue([
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
      {
        id: "aurora",
        title: "Aurora",
        category: "Developer Tools",
        summary: "Dark analytical interface.",
        swatches: ["#0f1115", "#0069fe"],
        surface: "web",
        source: "user",
        status: "draft",
        isEditable: true,
        enabled: true,
      },
    ])
    vi.mocked(getDesignSystem).mockImplementation(async (id) => ({
      id,
      title: id === "aurora" ? "Aurora" : "Vercel",
      category: "Developer Tools",
      summary: id === "aurora" ? "Dark analytical interface." : "Black and white precision.",
      swatches: ["#ffffff", "#171717"],
      surface: "web",
      source: id === "aurora" ? "user" : "built-in",
      status: id === "aurora" ? "draft" : "published",
      isEditable: id === "aurora",
      enabled: true,
      body: `# ${id}`,
      files: [{ path: "DESIGN.md", name: "DESIGN.md", kind: "document" }],
    }))
    vi.mocked(createDesignSystem).mockResolvedValue({
      id: "linear",
      title: "Linear",
      category: "Productivity & SaaS",
      summary: "Issue tracker.",
      swatches: [],
      surface: "web",
      source: "user",
      status: "draft",
      isEditable: true,
      enabled: true,
      body: "# Linear",
    })
    vi.mocked(updateDesignSystem).mockResolvedValue({
      id: "aurora",
      title: "Aurora",
      category: "Developer Tools",
      summary: "Dark analytical interface.",
      swatches: [],
      surface: "web",
      source: "user",
      status: "published",
      isEditable: true,
      enabled: true,
      body: "# Aurora",
    })
    vi.mocked(deleteDesignSystem).mockResolvedValue(undefined)
  })

  it("lists, filters, and opens built-in design system details", async () => {
    renderPage()

    expect(await screen.findByText("Vercel")).toBeVisible()
    fireEvent.change(screen.getByPlaceholderText("搜索设计系统..."), { target: { value: "aurora" } })

    expect(screen.queryByText("Vercel")).not.toBeInTheDocument()
    expect(screen.getByText("Aurora")).toBeVisible()

    fireEvent.change(screen.getByPlaceholderText("搜索设计系统..."), { target: { value: "vercel" } })
    fireEvent.click(await screen.findByText("Vercel"))

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toHaveTextContent("# vercel")
    })
    expect(screen.queryByRole("button", { name: "删除" })).not.toBeInTheDocument()
  })

  it("creates and manages editable user systems", async () => {
    renderPage()

    fireEvent.click(await screen.findByRole("button", { name: "新建设计系统" }))
    fireEvent.change(screen.getByPlaceholderText("标题，例如 Aurora"), { target: { value: "Linear" } })
    fireEvent.change(screen.getByPlaceholderText("一句话摘要"), { target: { value: "Issue tracker." } })
    fireEvent.click(screen.getByRole("button", { name: "创建" }))

    await waitFor(() => {
      expect(vi.mocked(createDesignSystem).mock.calls[0]?.[0]).toEqual(
        expect.objectContaining({ title: "Linear", summary: "Issue tracker." }),
      )
    })

    fireEvent.click(await screen.findByText("Aurora"))
    fireEvent.click(await screen.findByRole("button", { name: "发布" }))
    await waitFor(() => {
      expect(vi.mocked(updateDesignSystem)).toHaveBeenCalledWith("aurora", { status: "published" })
    })

    fireEvent.click(screen.getByRole("button", { name: "删除" }))
    await waitFor(() => {
      expect(vi.mocked(deleteDesignSystem).mock.calls[0]?.[0]).toBe("aurora")
    })
  })
})
