import { apiClient } from "@/lib/api-client"

export async function runAwel(input: string) {
  const res = await apiClient.post("/v1/awel/run", { initial_input: input })
  return res.data
}

export async function listOperators() {
  const res = await apiClient.get("/v1/awel/operators")
  return res.data as unknown[]
}
