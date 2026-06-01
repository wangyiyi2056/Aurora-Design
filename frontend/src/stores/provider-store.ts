import { create } from "zustand"
import { persist } from "zustand/middleware"
import { defaultByokConfig } from "@/state/config"

export interface AgentModelChoice {
  model?: string
  reasoning?: string
}

export type ProviderMode = "daemon" | "api" | "embedding"
export type ApiProtocol = "openai" | "anthropic" | "azure" | "google"

export interface ByokConfig {
  protocol: ApiProtocol
  baseUrl: string
  apiKey: string
  model: string
  apiVersion?: string
}

export interface EmbeddingConfig {
  binding: "ollama"
  host: string
  model: string
  dim: number
}

const DEFAULT_EMBEDDING_CONFIG: EmbeddingConfig = {
  binding: "ollama",
  host: "http://localhost:11434",
  model: "nomic-embed-text",
  dim: 768,
}

interface ProviderState {
  mode: ProviderMode
  byok: ByokConfig
  apiProtocolConfigs: Partial<Record<ApiProtocol, ByokConfig>>
  selectedAgentId: string | null
  agentModels: Record<string, AgentModelChoice>
  embeddingConfig: EmbeddingConfig
  embeddingSavedId: string | null
  embeddingTested: boolean
  chatSavedId: string | null
  chatSavedType: "daemon" | "api" | null
  setMode: (mode: ProviderMode) => void
  setEmbeddingTested: (tested: boolean) => void
  setByok: (config: Partial<ByokConfig>) => void
  setApiProtocol: (protocol: ApiProtocol) => void
  setSelectedAgentId: (agentId: string | null) => void
  setAgentModelChoice: (agentId: string, choice: AgentModelChoice) => void
  setEmbeddingConfig: (config: Partial<EmbeddingConfig>) => void
  setEmbeddingSavedId: (id: string | null) => void
  setChatSaved: (id: string | null, type: "daemon" | "api" | null) => void
}

export const useProviderStore = create<ProviderState>()(
  persist(
    (set) => ({
      mode: "daemon",
      byok: defaultByokConfig("anthropic"),
      apiProtocolConfigs: {
        anthropic: defaultByokConfig("anthropic"),
      },
      selectedAgentId: null,
      agentModels: {},
      embeddingConfig: DEFAULT_EMBEDDING_CONFIG,
      embeddingSavedId: null,
      embeddingTested: false,
      chatSavedId: null,
      chatSavedType: null,
      setMode: (mode) => set({ mode }),
      setByok: (config) =>
        set((state) => ({
          byok: (() => {
            const next = {
            ...state.byok,
            ...config,
              protocol: config.protocol ?? state.byok.protocol,
            }
            return next
          })(),
          apiProtocolConfigs: (() => {
            const next = {
              ...state.byok,
              ...config,
              protocol: config.protocol ?? state.byok.protocol,
            }
            return {
              ...state.apiProtocolConfigs,
              [next.protocol]: next,
            }
          })(),
        })),
      setApiProtocol: (protocol) =>
        set((state) => {
          const saved = state.apiProtocolConfigs[protocol]
          return {
            byok: saved ? { ...saved, protocol } : defaultByokConfig(protocol),
            apiProtocolConfigs: {
              ...state.apiProtocolConfigs,
              [state.byok.protocol]: state.byok,
              [protocol]: saved ? { ...saved, protocol } : defaultByokConfig(protocol),
            },
          }
        }),
      setSelectedAgentId: (agentId) => set({ selectedAgentId: agentId }),
      setAgentModelChoice: (agentId, choice) =>
        set((state) => ({
          agentModels: {
            ...state.agentModels,
            [agentId]: {
              ...(state.agentModels[agentId] ?? {}),
              ...choice,
            },
          },
        })),
      setEmbeddingConfig: (config) =>
        set((state) => ({
          embeddingConfig: { ...state.embeddingConfig, ...config },
        })),
      setEmbeddingSavedId: (id) => set({ embeddingSavedId: id }),
      setEmbeddingTested: (tested) => set({ embeddingTested: tested }),
      setChatSaved: (id, type) => set({ chatSavedId: id, chatSavedType: type }),
    }),
    {
      name: "aurora-provider-store",
      merge: (persisted, current) => {
        const saved = persisted as Partial<ProviderState> | undefined
        const byok = saved?.byok ?? current.byok
        return {
          ...current,
          ...saved,
          byok,
          apiProtocolConfigs: {
            ...current.apiProtocolConfigs,
            ...(saved?.apiProtocolConfigs ?? {}),
            [byok.protocol]: byok,
          },
          embeddingConfig: {
            ...DEFAULT_EMBEDDING_CONFIG,
            ...(saved?.embeddingConfig ?? {}),
          },
        }
      },
    }
  )
)
