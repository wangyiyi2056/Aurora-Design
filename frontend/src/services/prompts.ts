import { apiClient } from "@/lib/api-client"

export interface PromptTemplate {
  id: string
  name: string
  category: string
  template: string
  variables: string[]
  version: number
  enabled: boolean
  description: string
  created_at: number
  updated_at: number
}

export interface PromptPayload {
  name: string
  category?: string
  template: string
  variables?: string[]
  version?: number
  enabled?: boolean
  description?: string
}

export async function listPrompts(category?: string): Promise<{ items: PromptTemplate[] }> {
  const query = category ? `?category=${encodeURIComponent(category)}` : ""
  const res = await apiClient.get(`/v1/prompts${query}`)
  return res.data
}

export async function createPrompt(payload: PromptPayload): Promise<PromptTemplate> {
  const res = await apiClient.post("/v1/prompts", payload)
  return res.data
}

export async function updatePrompt(
  id: string,
  payload: Partial<PromptPayload>
): Promise<PromptTemplate> {
  const res = await apiClient.put(`/v1/prompts/${id}`, payload)
  return res.data
}

export async function deletePrompt(id: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/prompts/${id}`)
  return res.data
}

export async function renderPrompt(
  id: string,
  variables: Record<string, unknown>
): Promise<{ content: string }> {
  const res = await apiClient.post(`/v1/prompts/${id}/render`, { variables })
  return res.data
}
