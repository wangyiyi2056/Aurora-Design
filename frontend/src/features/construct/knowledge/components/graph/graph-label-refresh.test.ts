import { beforeEach, describe, expect, it } from "vitest"

import {
  getGraphRefreshLabel,
  normalizeGraphQueryLabel,
  requestGraphLabelRefresh,
  shouldFallbackEmptyLabelToGlobal,
} from "./graph-label-refresh"
import { useGraphStore } from "../../stores/graph"
import { useSettingsStore } from "../../stores/settings"

describe("graph label refresh", () => {
  beforeEach(() => {
    const graphState = useGraphStore.getState()
    graphState.reset()
    graphState.setGraphDataFetchAttempted(true)
    graphState.setLabelsFetchAttempted(true)
    graphState.setGraphIsEmpty(true)
    graphState.setLastSuccessfulQueryLabel("stale-label")
    useSettingsStore.getState().setQueryLabel("stale-label")
  })

  it("normalizes empty selections and overflow marker to global graph label", () => {
    expect(normalizeGraphQueryLabel("")).toBe("*")
    expect(normalizeGraphQueryLabel("   ")).toBe("*")
    expect(normalizeGraphQueryLabel("...")).toBe("*")
    expect(normalizeGraphQueryLabel(" Entity A ")).toBe("Entity A")
  })

  it("clears stale empty-graph state before requesting the selected label", () => {
    const initialVersion = useGraphStore.getState().graphDataVersion

    const selectedLabel = requestGraphLabelRefresh("*")

    const graphState = useGraphStore.getState()
    expect(selectedLabel).toBe("*")
    expect(useSettingsStore.getState().queryLabel).toBe("*")
    expect(graphState.graphDataFetchAttempted).toBe(false)
    expect(graphState.labelsFetchAttempted).toBe(false)
    expect(graphState.graphIsEmpty).toBe(false)
    expect(graphState.lastSuccessfulQueryLabel).toBe("")
    expect(graphState.graphDataVersion).toBeGreaterThan(initialVersion)
  })

  it("refreshes the currently selected label even when the graph is empty", () => {
    expect(getGraphRefreshLabel("stale-label", true)).toBe("stale-label")
    expect(getGraphRefreshLabel("*", true)).toBe("*")
    expect(getGraphRefreshLabel("stale-label", false)).toBe("stale-label")
  })

  it("does not fall back to global when a non-global label returns no graph data", () => {
    expect(shouldFallbackEmptyLabelToGlobal("stale-label", false)).toBe(false)
    expect(shouldFallbackEmptyLabelToGlobal("*", false)).toBe(false)
    expect(shouldFallbackEmptyLabelToGlobal("stale-label", true)).toBe(false)
  })

})
