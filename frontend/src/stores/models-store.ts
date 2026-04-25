import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ModelItem {
  id: string
  name: string
  type: string
  baseUrl: string
  apiKey: string
  status: "untested" | "testing" | "available" | "error"
  statusMessage?: string
}

interface ModelsState {
  models: ModelItem[]
  addModel: (model: Omit<ModelItem, "id" | "status" | "statusMessage">) => void
  updateModel: (id: string, updates: Partial<ModelItem>) => void
  removeModel: (id: string) => void
}

export const useModelsStore = create<ModelsState>()(
  persist(
    (set) => ({
      models: [],
      addModel: (model) =>
        set((state) => ({
          models: [
            ...state.models,
            {
              id: Date.now().toString(),
              ...model,
              status: "untested",
            },
          ],
        })),
      updateModel: (id, updates) =>
        set((state) => ({
          models: state.models.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          ),
        })),
      removeModel: (id) =>
        set((state) => ({
          models: state.models.filter((m) => m.id !== id),
        })),
    }),
    { name: "chatbi-models-store" }
  )
)
