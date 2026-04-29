import { apiClient } from "@/lib/api-client"

export interface ModelItem {
  id: string
  name: string
  type: string
  baseUrl: string
  apiKey: string
  status: "untested" | "testing" | "available" | "error"
  statusMessage?: string
  isDefault?: boolean
}

interface APIModelItem {
  id: string
  name: string
  type: string
  base_url: string
  api_key: string
  is_default: boolean
  status: "untested" | "testing" | "available" | "error"
  status_message?: string | null
}

export interface ModelConfigPayload {
  name: string
  type: string
  base_url: string
  api_key?: string
  is_default?: boolean
}

function fromAPIModel(item: APIModelItem): ModelItem {
  return {
    id: item.id,
    name: item.name,
    type: item.type,
    baseUrl: item.base_url,
    apiKey: item.api_key,
    status: item.status,
    statusMessage: item.status_message || undefined,
    isDefault: item.is_default,
  }
}

export async function listModelConfigs(): Promise<{ items: ModelItem[] }> {
  const res = await apiClient.get("/v1/models")
  return { items: (res.data.items || []).map(fromAPIModel) }
}

export async function createModelConfig(payload: ModelConfigPayload): Promise<ModelItem> {
  const res = await apiClient.post("/v1/models", payload)
  return fromAPIModel(res.data)
}

export async function updateModelConfig(
  id: string,
  payload: Partial<ModelConfigPayload>
): Promise<ModelItem> {
  const res = await apiClient.put(`/v1/models/${id}`, payload)
  return fromAPIModel(res.data)
}

export async function deleteModelConfig(id: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/models/${id}`)
  return res.data
}

export async function testSavedModelConnection(id: string) {
  const res = await apiClient.post(`/v1/models/${id}/test`)
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
