import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import PromptPage from "./prompt-page"
import {
  createPrompt,
  deletePrompt,
  getSystemPrompt,
  listCustomPrompts,
  saveSystemPrompt,
} from "@/services/prompts"

vi.mock("@/features/construct/components/construct-shell", () => ({
  ConstructShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/services/prompts", () => ({
  createPrompt: vi.fn(),
  deletePrompt: vi.fn(),
  getSystemPrompt: vi.fn(),
  listCustomPrompts: vi.fn(),
  saveSystemPrompt: vi.fn(),
}))

function renderPromptPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <PromptPage />
    </QueryClientProvider>,
  )
}

describe("PromptPage", () => {
  beforeEach(() => {
    vi.mocked(getSystemPrompt).mockResolvedValue({
      id: "system",
      name: "global-system-prompt",
      category: "system",
      template: "Existing system prompt",
      variables: [],
      version: 1,
      enabled: true,
      description: "",
      extra: { prompt_type: "system" },
      created_at: 1,
      updated_at: 1,
    })
    vi.mocked(listCustomPrompts).mockResolvedValue({
      items: [
        {
          id: "custom-1",
          name: "dashboard",
          category: "general",
          template: "Use dense dashboards.",
          variables: [],
          version: 1,
          enabled: true,
          description: "Dashboard prompt",
          extra: { prompt_type: "custom" },
          created_at: 1,
          updated_at: 1,
        },
      ],
    })
    vi.mocked(saveSystemPrompt).mockResolvedValue({
      id: "system",
      name: "global-system-prompt",
      category: "system",
      template: "Updated system prompt",
      variables: [],
      version: 1,
      enabled: true,
      description: "",
      extra: { prompt_type: "system" },
      created_at: 1,
      updated_at: 2,
    })
    vi.mocked(createPrompt).mockResolvedValue({
      id: "custom-2",
      name: "landing",
      category: "general",
      template: "Use landing page guidance.",
      variables: [],
      version: 1,
      enabled: true,
      description: "",
      extra: { prompt_type: "custom" },
      created_at: 2,
      updated_at: 2,
    })
    vi.mocked(deletePrompt).mockResolvedValue({ success: true })
  })

  it("loads and saves the system prompt", async () => {
    renderPromptPage()

    const textarea = await screen.findByTestId("system-prompt-textarea")
    await waitFor(() => {
      expect(textarea).toHaveValue("Existing system prompt")
    })

    fireEvent.change(textarea, { target: { value: "Updated system prompt" } })
    fireEvent.click(screen.getByRole("button", { name: "保存系统提示词" }))

    await waitFor(() => {
      expect(vi.mocked(saveSystemPrompt).mock.calls[0]?.[0]).toBe("Updated system prompt")
    })
  })

  it("creates and deletes custom prompts", async () => {
    renderPromptPage()

    const customTab = screen.getByRole("tab", { name: "自定义提示词" })
    fireEvent.mouseDown(customTab, { button: 0, ctrlKey: false })
    fireEvent.click(customTab)
    expect(await screen.findByText("dashboard")).toBeVisible()

    fireEvent.click(screen.getByRole("button", { name: "新增提示词" }))
    expect(screen.getByRole("dialog", { name: "新增自定义提示词" })).toBeVisible()

    fireEvent.change(screen.getByPlaceholderText("名称"), { target: { value: "landing" } })
    fireEvent.change(screen.getByPlaceholderText("提示词内容"), {
      target: { value: "Use landing page guidance." },
    })
    fireEvent.click(screen.getByRole("button", { name: "保存提示词" }))

    await waitFor(() => {
      expect(vi.mocked(createPrompt).mock.calls[0]?.[0]).toEqual(
        expect.objectContaining({
          name: "landing",
          template: "Use landing page guidance.",
          variables: [],
          enabled: true,
        }),
      )
    })

    fireEvent.click(screen.getByRole("button", { name: "删除" }))
    await waitFor(() => {
      expect(vi.mocked(deletePrompt).mock.calls[0]?.[0]).toBe("custom-1")
    })
  })
})
