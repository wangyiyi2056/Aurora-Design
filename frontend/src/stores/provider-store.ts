import { create } from "zustand"
import { persist } from "zustand/middleware"
import { defaultByokConfig } from "@/state/config"

export interface AgentModelChoice {
  model?: string
  reasoning?: string
}

export type ProviderMode = "daemon" | "api"
export type ApiProtocol = "openai" | "anthropic" | "azure" | "google"

export interface ByokConfig {
  protocol: ApiProtocol
  baseUrl: string
  apiKey: string
  model: string
  apiVersion?: string
}

interface ProviderState {
  mode: ProviderMode
  byok: ByokConfig
  apiProtocolConfigs: Partial<Record<ApiProtocol, ByokConfig>>
  selectedAgentId: string | null
  agentModels: Record<string, AgentModelChoice>
  setMode: (mode: ProviderMode) => void
  setByok: (config: Partial<ByokConfig>) => void
  setApiProtocol: (protocol: ApiProtocol) => void
  setSelectedAgentId: (agentId: string | null) => void
  setAgentModelChoice: (agentId: string, choice: AgentModelChoice) => void
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
        }
      },
    }
  )
)
