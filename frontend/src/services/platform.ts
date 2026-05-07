import { apiClient } from "@/lib/api-client"

export interface FeedbackItem {
  id: string
  target_type: string
  target_id: string
  rating: number
  comment: string
  extra: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface TraceEvent {
  id: string
  name: string
  span_type: string
  metadata: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface PlatformUser {
  id: string
  username: string
  display_name: string
  role: string
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export async function createFeedback(payload: {
  target_type: string
  target_id: string
  rating?: number
  comment?: string
  extra?: Record<string, unknown>
}): Promise<FeedbackItem> {
  const res = await apiClient.post("/v1/feedback", payload)
  return res.data
}

export async function listFeedback(): Promise<{ items: FeedbackItem[] }> {
  const res = await apiClient.get("/v1/feedback")
  return res.data
}

export async function getFeedback(id: string): Promise<FeedbackItem> {
  const res = await apiClient.get(`/v1/feedback/${id}`)
  return res.data
}

export async function updateFeedback(
  id: string,
  payload: Partial<Pick<FeedbackItem, "target_type" | "target_id" | "rating" | "comment" | "extra">>
): Promise<FeedbackItem> {
  const res = await apiClient.put(`/v1/feedback/${id}`, payload)
  return res.data
}

export async function deleteFeedback(id: string): Promise<{ deleted: boolean }> {
  const res = await apiClient.delete(`/v1/feedback/${id}`)
  return res.data
}

export async function createTrace(payload: {
  name: string
  span_type?: string
  metadata?: Record<string, unknown>
}): Promise<TraceEvent> {
  const res = await apiClient.post("/v1/traces", payload)
  return res.data
}

export async function listTraces(): Promise<{ items: TraceEvent[] }> {
  const res = await apiClient.get("/v1/traces")
  return res.data
}

export async function getTrace(id: string): Promise<TraceEvent> {
  const res = await apiClient.get(`/v1/traces/${id}`)
  return res.data
}

export async function updateTrace(
  id: string,
  payload: Partial<Pick<TraceEvent, "name" | "span_type" | "metadata">>
): Promise<TraceEvent> {
  const res = await apiClient.put(`/v1/traces/${id}`, payload)
  return res.data
}

export async function deleteTrace(id: string): Promise<{ deleted: boolean }> {
  const res = await apiClient.delete(`/v1/traces/${id}`)
  return res.data
}

export async function listUsers(): Promise<{ items: PlatformUser[] }> {
  const res = await apiClient.get("/v1/users")
  return res.data
}

export async function createUser(payload: {
  username: string
  display_name?: string
  role?: string
  enabled?: boolean
}): Promise<PlatformUser> {
  const res = await apiClient.post("/v1/users", payload)
  return res.data
}

export async function getUser(id: string): Promise<PlatformUser> {
  const res = await apiClient.get(`/v1/users/${id}`)
  return res.data
}

export async function updateUser(
  id: string,
  payload: Partial<Pick<PlatformUser, "username" | "display_name" | "role" | "enabled">>
): Promise<PlatformUser> {
  const res = await apiClient.put(`/v1/users/${id}`, payload)
  return res.data
}

export async function deleteUser(id: string): Promise<{ deleted: boolean }> {
  const res = await apiClient.delete(`/v1/users/${id}`)
  return res.data
}
