import { apiClient } from "@/lib/api-client"

export interface DesignSkillSummary {
  id: string
  name: string
  description: string
  source: string
  mode: string
  surface: string
  scenario: string
  previewType: string
  examplePrompt: string
  hasAssets: boolean
  hasReferences: boolean
  triggers: string[]
  body: string | null
  hidden: boolean
  status: string
  adapterKind: string
  dependencyType: string
  requiredTools: string[]
}

export interface DesignSkillDetail extends DesignSkillSummary {
  body: string
  files: string[]
}

export interface DesignSkillAdapterBacklogItem {
  id: string
  name: string
  description: string
  source: string
  status: string
  dependencyType: string
  requiredTools: string[]
}

export interface DesignSkillAdapterBacklogGroup {
  count: number
  items: DesignSkillAdapterBacklogItem[]
}

export interface DesignSkillAdapterBacklog {
  totalPending: number
  groups: Record<string, DesignSkillAdapterBacklogGroup>
}

export async function listDesignSkills(options?: { includeHidden?: boolean }): Promise<DesignSkillSummary[]> {
  const response = await apiClient.get<{ skills: DesignSkillSummary[] }>("/v1/design-skills", {
    params: options?.includeHidden ? { include_hidden: true } : undefined,
  })
  return response.data.skills
}

export async function getDesignSkill(id: string): Promise<DesignSkillDetail> {
  const response = await apiClient.get<DesignSkillDetail>(`/v1/design-skills/${encodeURIComponent(id)}`)
  return response.data
}

export async function getDesignSkillAdapterBacklog(): Promise<DesignSkillAdapterBacklog> {
  const response = await apiClient.get<DesignSkillAdapterBacklog>("/v1/design-skills/adapters")
  return response.data
}

export async function updateDesignSkillManagement(
  id: string,
  update: { hidden?: boolean; status?: string },
): Promise<DesignSkillSummary> {
  const response = await apiClient.patch<DesignSkillSummary>(
    `/v1/design-skills/${encodeURIComponent(id)}/management`,
    update,
  )
  return response.data
}
