import { apiClient } from "@/lib/api-client"

export async function listSkills() {
  const res = await apiClient.get("/v1/agent/skills")
  return res.data as Record<string, string>
}
