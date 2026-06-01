import { apiClient } from "@/lib/api-client"

export interface AgentInfo {
  id: string
  name: string
  bin: string
  available: boolean
  path?: string
  version?: string | null
  models?: { id: string; label: string }[]
  reasoningOptions?: { id: string; label: string }[]
  streamFormat?: string
  promptViaStdin?: boolean
}

export async function listAgents(): Promise<{ agents: AgentInfo[] }> {
  const res = await apiClient.get("/v1/agents")
  return res.data
}

export interface SkillInfo {
  name: string
  description: string
  description_cn: string
  parameters: Record<string, unknown>
  is_builtin: boolean
}

export interface SkillsListResponse {
  skills: SkillInfo[]
  total: number
}

export async function listSkills(): Promise<Record<string, string>> {
  const res = await apiClient.get("/v1/agent/skills")
  return res.data as Record<string, string>
}

export async function listSkillsDetail(): Promise<SkillsListResponse> {
  const res = await apiClient.get("/v1/skills")
  return res.data as SkillsListResponse
}

// ── Model configuration ───────────────────────────────────────────────

export interface ModelConfigResponse {
  id: string
  name: string
  type: string
  base_url: string
  api_key: string
  is_default: boolean
  status: string
  status_message: string | null
}

export async function createModelConfig(
  data: {
    name: string
    type: string
    base_url: string
    api_key: string
    is_default?: boolean
  }
): Promise<ModelConfigResponse> {
  const res = await apiClient.post("/v1/models", data)
  return res.data
}

export async function updateModelConfig(
  modelId: string,
  data: Partial<{
    name: string
    type: string
    base_url: string
    api_key: string
    is_default: boolean
  }>
): Promise<ModelConfigResponse> {
  const res = await apiClient.put(`/v1/models/${modelId}`, data)
  return res.data
}

export async function deleteModelConfig(modelId: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/models/${modelId}`)
  return res.data
}

export async function listModelConfigs(): Promise<{ items: ModelConfigResponse[] }> {
  const res = await apiClient.get("/v1/models")
  return res.data
}

// ── Embedding ─────────────────────────────────────────────────────────

export interface EmbeddingTestResult {
  success: boolean
  message: string
  model_info: { model: string; dimension: number; provider: string } | null
}

export async function testEmbeddingConnection(
  host: string,
  model: string
): Promise<EmbeddingTestResult> {
  const res = await apiClient.post("/v1/models/test-embedding", { host, model })
  return res.data
}

export interface ModelReadiness {
  llm: boolean
  embedding: boolean
  query_engine: boolean
}

export async function getModelReadiness(): Promise<ModelReadiness> {
  const res = await apiClient.get("/v1/models/readiness")
  return res.data
}
