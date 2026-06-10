import "@testing-library/jest-dom/vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { QueryPanel } from "./QueryPanel"
import { useSettingsStore } from "../stores/settings"

const mockAddEntry = vi.fn()
const mockMutateAsync = vi.fn()

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}))

vi.mock("../hooks/use-knowledge-v2", () => ({
  useQueryKnowledgeData: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}))

vi.mock("../hooks/useQueryHistory", () => ({
  useQueryHistory: () => ({
    entries: [],
    addEntry: mockAddEntry,
    removeEntry: vi.fn(),
    clearAll: vi.fn(),
    updateEntry: vi.fn(),
  }),
}))

vi.mock("./QueryHistory", () => ({
  QueryHistory: () => <div>history</div>,
}))

function createNdjsonResponse(lines: string[]) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line))
      }
      controller.close()
    },
  })

  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson" },
  })
}

describe("QueryPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    localStorage.clear()
    useSettingsStore.setState({
      retrievalHistory: [],
      querySettings: {
        mode: "mix",
        top_k: 40,
        chunk_top_k: 20,
        max_entity_tokens: 6000,
        max_relation_tokens: 8000,
        max_total_tokens: 30000,
        only_need_context: false,
        only_need_prompt: false,
        stream: true,
        history_turns: 0,
        user_prompt: "",
        enable_rerank: true,
      },
    })
    Object.assign(globalThis, {
      fetch: vi.fn(),
    })
  })

  it("clears references and hides copy when the stream ends with an error", async () => {
    vi.mocked(fetch).mockResolvedValue(
      createNdjsonResponse([
        JSON.stringify({
          references: [{ reference_id: "1", file_path: "配方模板.txt" }],
        }) + "\n",
        JSON.stringify({ error: "Connection error." }) + "\n",
      ]),
    )

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "配方管理" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(
        screen.getByText(
          (_, node) =>
            node?.tagName.toLowerCase() === "p" &&
            node.textContent === "Error: Connection error.",
        ),
      ).toBeInTheDocument()
    })

    expect(screen.queryByText("References")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Copy response")).not.toBeInTheDocument()
    expect(mockAddEntry).not.toHaveBeenCalled()
  })

  it("does not send prior turns by default", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        createNdjsonResponse([
          JSON.stringify({ response: "第一答" }) + "\n",
        ]),
      )
      .mockResolvedValueOnce(
        createNdjsonResponse([
          JSON.stringify({ response: "第二答" }) + "\n",
        ]),
      )

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "第一问" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(screen.getByText("第一答")).toBeInTheDocument()
    })

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "继续说明" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(screen.getByText("第二答")).toBeInTheDocument()
    })

    expect(fetch).toHaveBeenCalledTimes(2)
    const secondBody = JSON.parse(String(vi.mocked(fetch).mock.calls[1][1]?.body))

    expect(secondBody).toMatchObject({
      query: "继续说明",
      conversation_history: [],
    })
  })

  it("sends prior successful turns when history turns is enabled", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        createNdjsonResponse([
          JSON.stringify({ response: "第一答" }) + "\n",
        ]),
      )
      .mockResolvedValueOnce(
        createNdjsonResponse([
          JSON.stringify({ response: "第二答" }) + "\n",
        ]),
      )

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "第一问" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(screen.getByText("第一答")).toBeInTheDocument()
    })

    useSettingsStore.getState().updateQuerySettings({ history_turns: 1 })

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "继续说明" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(screen.getByText("第二答")).toBeInTheDocument()
    })

    const secondBody = JSON.parse(String(vi.mocked(fetch).mock.calls[1][1]?.body))

    expect(secondBody).toMatchObject({
      query: "继续说明",
      conversation_history: [
        { role: "user", content: "第一问" },
        { role: "assistant", content: "第一答" },
      ],
    })
  })

  it("automatically sends recent turns for bypass mode when history turns is disabled", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(createNdjsonResponse([JSON.stringify({ response: "第一答" }) + "\n"]))
      .mockResolvedValueOnce(createNdjsonResponse([JSON.stringify({ response: "第二答" }) + "\n"]))

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "第一问" } })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))
    await waitFor(() => expect(screen.getByText("第一答")).toBeInTheDocument())

    useSettingsStore.getState().updateQuerySettings({ mode: "bypass" })

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "继续说明" } })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))
    await waitFor(() => expect(screen.getByText("第二答")).toBeInTheDocument())

    const secondBody = JSON.parse(String(vi.mocked(fetch).mock.calls[1][1]?.body))

    expect(secondBody).toMatchObject({
      mode: "bypass",
      query: "继续说明",
      conversation_history: [
        { role: "user", content: "第一问" },
        { role: "assistant", content: "第一答" },
      ],
    })
  })

  it("supports one-off query mode prefixes without changing displayed user text", async () => {
    vi.mocked(fetch).mockResolvedValue(
      createNdjsonResponse([JSON.stringify({ response: "局部回答" }) + "\n"]),
    )

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "/local 介绍A" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => expect(screen.getByText("局部回答")).toBeInTheDocument())
    expect(screen.getByText("/local 介绍A")).toBeInTheDocument()

    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))
    expect(body).toMatchObject({
      mode: "local",
      query: "介绍A",
    })
  })

  it("rejects invalid query mode prefixes before calling the API", async () => {
    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "/unknown 介绍A" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    expect(fetch).not.toHaveBeenCalled()
    expect(
      screen.getByText("Invalid query mode. Use /naive, /local, /global, /hybrid, /mix, or /bypass."),
    ).toBeInTheDocument()
  })

  it("processes a final NDJSON buffer without a trailing newline", async () => {
    vi.mocked(fetch).mockResolvedValue(
      createNdjsonResponse([JSON.stringify({ response: "最后一段" })]),
    )

    render(<QueryPanel knowledgeName="demo-kb" />)

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "无换行测试" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Send query" }))

    await waitFor(() => {
      expect(screen.getByText("最后一段")).toBeInTheDocument()
    })
  })
})
