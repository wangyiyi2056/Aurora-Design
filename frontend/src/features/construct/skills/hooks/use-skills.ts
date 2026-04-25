import { useQuery } from "@tanstack/react-query"
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

export async function listSkillsDetail(): Promise<SkillsListResponse> {
  const res = await apiClient.get("/v1/skills")
  return res.data as SkillsListResponse
}

export function useSkills() {
  return useQuery<SkillsListResponse>({
    queryKey: ["skills", "list"],
    queryFn: listSkillsDetail,
  })
}

export function useSkillsSimple() {
  return useQuery<Record<string, string>>({
    queryKey: ["skills", "simple"],
    queryFn: async () => {
      const res = await listSkillsDetail()
      const map: Record<string, string> = {}
      for (const s of res.skills) {
        map[s.name] = s.description_cn || s.description
      }
      return map
    },
  })
}
