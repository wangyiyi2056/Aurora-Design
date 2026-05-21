import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { WorkspaceTabsState } from "../types"

interface WorkspaceTabsStore {
  byWorkspace: Record<string, WorkspaceTabsState>
  getTabsState: (workspaceId: string) => WorkspaceTabsState
  setTabsState: (workspaceId: string, next: WorkspaceTabsState) => void
}

const emptyState: WorkspaceTabsState = { tabs: [], active: null }

export const useWorkspaceTabsStore = create<WorkspaceTabsStore>()(
  persist(
    (set, get) => ({
      byWorkspace: {},
      getTabsState: (workspaceId) => get().byWorkspace[workspaceId] ?? emptyState,
      setTabsState: (workspaceId, next) =>
        set((state) => ({
          byWorkspace: {
            ...state.byWorkspace,
            [workspaceId]: next,
          },
        })),
    }),
    { name: "aurora-workspace-tabs" },
  ),
)
