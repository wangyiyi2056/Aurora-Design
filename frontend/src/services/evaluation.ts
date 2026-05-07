import { apiClient } from "@/lib/api-client"

export interface EvaluationDataset {
  id: string
  name: string
  description: string
  data?: unknown
  created_at?: string
  updated_at?: string
}

export interface EvaluationTask {
  id: string
  name: string
  model: string
  dataset_id: string
  status: "pending" | "running" | "completed" | "failed" | string
  result?: unknown
  created_at?: string
  updated_at?: string
}

export async function listEvaluationDatasets(): Promise<{ items: EvaluationDataset[] }> {
  const res = await apiClient.get("/v1/evaluation/datasets")
  return res.data
}

export async function createEvaluationDataset(payload: {
  name: string
  description?: string
  data?: unknown
}): Promise<EvaluationDataset> {
  const res = await apiClient.post("/v1/evaluation/datasets", payload)
  return res.data
}

export async function getEvaluationDataset(id: string): Promise<EvaluationDataset> {
  const res = await apiClient.get(`/v1/evaluation/datasets/${id}`)
  return res.data
}

export async function updateEvaluationDataset(
  id: string,
  payload: Partial<Pick<EvaluationDataset, "name" | "description" | "data">>
): Promise<EvaluationDataset> {
  const res = await apiClient.put(`/v1/evaluation/datasets/${id}`, payload)
  return res.data
}

export async function deleteEvaluationDataset(id: string): Promise<{ deleted: boolean }> {
  const res = await apiClient.delete(`/v1/evaluation/datasets/${id}`)
  return res.data
}

export async function listEvaluationTasks(): Promise<{ items: EvaluationTask[] }> {
  const res = await apiClient.get("/v1/evaluation/tasks")
  return res.data
}

export async function createEvaluationTask(payload: {
  name: string
  model?: string
  dataset_id: string
  status?: string
  result?: unknown
}): Promise<EvaluationTask> {
  const res = await apiClient.post("/v1/evaluation/tasks", payload)
  return res.data
}

export async function getEvaluationTask(id: string): Promise<EvaluationTask> {
  const res = await apiClient.get(`/v1/evaluation/tasks/${id}`)
  return res.data
}

export async function updateEvaluationTask(
  id: string,
  payload: Partial<Pick<EvaluationTask, "name" | "model" | "dataset_id" | "status" | "result">>
): Promise<EvaluationTask> {
  const res = await apiClient.put(`/v1/evaluation/tasks/${id}`, payload)
  return res.data
}

export async function deleteEvaluationTask(id: string): Promise<{ deleted: boolean }> {
  const res = await apiClient.delete(`/v1/evaluation/tasks/${id}`)
  return res.data
}
