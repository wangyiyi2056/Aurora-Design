import { apiClient } from "@/lib/api-client"

export interface PluginItem {
  id: string
  name: string
  description: string
  entrypoint: string
  enabled: boolean
  config: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface PluginPayload {
  name: string
  description?: string
  entrypoint?: string
  enabled?: boolean
  config?: Record<string, unknown>
}

export async function listPlugins(): Promise<{ items: PluginItem[] }> {
  const res = await apiClient.get("/v1/plugins")
  return res.data
}

export async function createPlugin(payload: PluginPayload): Promise<PluginItem> {
  const res = await apiClient.post("/v1/plugins", payload)
  return res.data
}

export async function getPlugin(id: string): Promise<PluginItem> {
  const res = await apiClient.get(`/v1/plugins/${id}`)
  return res.data
}

export async function updatePlugin(
  id: string,
  payload: Partial<PluginPayload>
): Promise<PluginItem> {
  const res = await apiClient.put(`/v1/plugins/${id}`, payload)
  return res.data
}

export async function setPluginEnabled(id: string, enabled: boolean): Promise<PluginItem> {
  const res = await apiClient.post(`/v1/plugins/${id}/enable`, { enabled })
  return res.data
}

export async function disablePlugin(id: string): Promise<PluginItem> {
  const res = await apiClient.post(`/v1/plugins/${id}/disable`)
  return res.data
}

export async function deletePlugin(id: string) {
  const res = await apiClient.delete(`/v1/plugins/${id}`)
  return res.data as { success: boolean }
}
