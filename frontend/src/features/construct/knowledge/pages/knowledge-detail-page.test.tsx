import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import KnowledgeDetailPage from "./knowledge-detail-page"
import { useGraphStore } from "../stores/graph"
import { useSettingsStore } from "../stores/settings"

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ name: encodeURIComponent("demo-kb") }),
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}))

vi.mock("@/features/construct/components/construct-shell", () => ({
  ConstructShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock("../components/DocumentManager", () => ({
  DocumentManager: () => <div>documents</div>,
}))

vi.mock("../components/GraphViewer", () => ({
  GraphViewer: () => <div>graph</div>,
}))

vi.mock("../components/KnowledgeSettings", () => ({
  KnowledgeSettings: () => <div>settings</div>,
}))

vi.mock("../components/QueryPanel", () => ({
  QueryPanel: () => <div>query</div>,
}))

describe("KnowledgeDetailPage", () => {
  it("invalidates child tab data and resets graph fetch flags on leave", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    useGraphStore.getState().setGraphDataFetchAttempted(true)
    useGraphStore.getState().setLabelsFetchAttempted(true)
    useSettingsStore.getState().setQueryLabel("label-from-other-kb")
    const initialGraphVersion = useGraphStore.getState().graphDataVersion

    const { unmount } = render(
      <QueryClientProvider client={queryClient}>
        <KnowledgeDetailPage />
      </QueryClientProvider>,
    )

    expect(useSettingsStore.getState().queryLabel).toBe("*")

    unmount()

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "detail", "demo-kb"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "documents", "demo-kb"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "status-counts", "demo-kb"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "pipeline-status", "demo-kb"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "cache-stats", "demo-kb"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["knowledge", "v2", "graph", "demo-kb"] })

    const graphState = useGraphStore.getState()
    expect(graphState.graphDataFetchAttempted).toBe(false)
    expect(graphState.labelsFetchAttempted).toBe(false)
    expect(graphState.graphDataVersion).toBeGreaterThan(initialGraphVersion)
  })
})
