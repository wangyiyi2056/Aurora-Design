import { useGraphStore } from "../../stores/graph"
import { useSettingsStore } from "../../stores/settings"

export function normalizeGraphQueryLabel(label: string | null | undefined) {
  const trimmed = typeof label === "string" ? label.trim() : ""
  if (!trimmed || trimmed === "...") return "*"
  return trimmed
}

export function getGraphRefreshLabel(label: string | null | undefined, _graphIsEmpty: boolean) {
  return normalizeGraphQueryLabel(label)
}

export function shouldFallbackEmptyLabelToGlobal(
  _label: string | null | undefined,
  _hasGraphData: boolean,
) {
  return false
}


export function requestGraphLabelRefresh(label: string | null | undefined) {
  const nextLabel = normalizeGraphQueryLabel(label)
  const graphState = useGraphStore.getState()

  graphState.reset()
  graphState.setGraphDataFetchAttempted(false)
  graphState.setLabelsFetchAttempted(false)
  graphState.setLastSuccessfulQueryLabel("")
  useSettingsStore.getState().setQueryLabel(nextLabel)
  graphState.incrementGraphDataVersion()

  return nextLabel
}
