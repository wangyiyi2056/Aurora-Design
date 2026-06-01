import { apiClient } from "@/lib/api-client"

export interface DesignSystemFileSummary {
  path: string
  name: string
  kind: string
  size?: number
  updatedAt?: string
}

export interface DesignSystemSummary {
  id: string
  title: string
  name?: string
  category: string
  summary: string
  swatches: string[]
  surface: string
  source: string
  status: string
  isEditable: boolean
  enabled: boolean
  createdAt?: string | null
  updatedAt?: string | null
}

export interface DesignSystemDetail extends DesignSystemSummary {
  body: string
  files?: DesignSystemFileSummary[]
}

export interface DesignSystemInput {
  id?: string
  title?: string
  name?: string
  summary?: string
  category?: string
  surface?: string
  status?: string
  body?: string
}

export async function listDesignSystems(): Promise<DesignSystemSummary[]> {
  const response = await apiClient.get<{ designSystems: DesignSystemSummary[] }>("/v1/design-systems")
  return response.data.designSystems
}

export async function getDesignSystem(id: string): Promise<DesignSystemDetail> {
  const response = await apiClient.get<DesignSystemDetail>(`/v1/design-systems/${encodeURIComponent(id)}`)
  return response.data
}

export async function createDesignSystem(input: DesignSystemInput): Promise<DesignSystemDetail> {
  const response = await apiClient.post<DesignSystemDetail>("/v1/design-systems", input)
  return response.data
}

export async function updateDesignSystem(id: string, input: DesignSystemInput): Promise<DesignSystemDetail> {
  const response = await apiClient.patch<DesignSystemDetail>(`/v1/design-systems/${encodeURIComponent(id)}`, input)
  return response.data
}

export async function toggleDesignSystem(id: string): Promise<DesignSystemSummary> {
  const response = await apiClient.post<DesignSystemSummary>(`/v1/design-systems/${encodeURIComponent(id)}/toggle`)
  return response.data
}

export async function deleteDesignSystem(id: string): Promise<void> {
  await apiClient.delete(`/v1/design-systems/${encodeURIComponent(id)}`)
}

export function designSystemPreviewUrl(id: string, kind: "preview" | "showcase" = "preview"): string {
  return `/api/v1/design-systems/${encodeURIComponent(id)}/${kind}`
}
