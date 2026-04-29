import { apiClient } from "@/lib/api-client"

export interface AppItem {
  id: string
  name: string
  description: string
  type: string
  model: string
  published: boolean
  knowledge_ids: string[]
  datasource_ids: string[]
  skill_names: string[]
}

export interface AppPayload {
  name: string
  description: string
  type: string
  model: string
  published?: boolean
  knowledge_ids?: string[]
  datasource_ids?: string[]
  skill_names?: string[]
}

export async function listApps(): Promise<{ items: AppItem[] }> {
  const res = await apiClient.get("/v1/apps")
  return res.data
}

export async function createApp(payload: AppPayload): Promise<AppItem> {
  const res = await apiClient.post("/v1/apps", payload)
  return res.data
}

export async function updateApp(id: string, payload: Partial<AppPayload>): Promise<AppItem> {
  const res = await apiClient.put(`/v1/apps/${id}`, payload)
  return res.data
}

export async function deleteApp(id: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/apps/${id}`)
  return res.data
}

export async function publishApp(id: string, published: boolean): Promise<AppItem> {
  const res = await apiClient.post(`/v1/apps/${id}/publish`, { published })
  return res.data
}
