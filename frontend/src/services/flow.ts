import { apiClient } from "@/lib/api-client"

export interface FlowItem {
  id: string
  name: string
  description: string
  nodes: Record<string, unknown>[]
  edges: Record<string, unknown>[]
  variables: Record<string, unknown>
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface FlowRun {
  id: string
  flow_id: string
  status: string
  input: unknown
  output: unknown
  error?: string
  created_at?: string
  updated_at?: string
}

export interface FlowPayload {
  name: string
  description?: string
  nodes?: Record<string, unknown>[]
  edges?: Record<string, unknown>[]
  variables?: Record<string, unknown>
  enabled?: boolean
}

export async function runAwel(input: string) {
  const res = await apiClient.post("/v1/awel/run", { initial_input: input })
  return res.data
}

export async function listOperators() {
  const res = await apiClient.get("/v1/awel/operators")
  return res.data as unknown[]
}

export async function listFlows(): Promise<{ items: FlowItem[] }> {
  const res = await apiClient.get("/v1/awel/flows")
  return res.data
}

export async function createFlow(payload: FlowPayload): Promise<FlowItem> {
  const res = await apiClient.post("/v1/awel/flows", payload)
  return res.data
}

export async function getFlow(flowId: string): Promise<FlowItem> {
  const res = await apiClient.get(`/v1/awel/flows/${flowId}`)
  return res.data
}

export async function updateFlow(
  flowId: string,
  payload: Partial<FlowPayload>
): Promise<FlowItem> {
  const res = await apiClient.put(`/v1/awel/flows/${flowId}`, payload)
  return res.data
}

export async function deleteFlow(flowId: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/awel/flows/${flowId}`)
  return res.data
}

export async function runFlow(flowId: string, input: unknown): Promise<FlowRun> {
  const res = await apiClient.post(`/v1/awel/flows/${flowId}/run`, {
    initial_input: input,
  })
  return res.data
}

export async function listFlowRuns(flowId: string): Promise<{ items: FlowRun[] }> {
  const res = await apiClient.get(`/v1/awel/flows/${flowId}/runs`)
  return res.data
}

export async function getFlowRun(runId: string): Promise<FlowRun> {
  const res = await apiClient.get(`/v1/awel/runs/${runId}`)
  return res.data
}
