import { apiClient } from "@/lib/api-client"

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
