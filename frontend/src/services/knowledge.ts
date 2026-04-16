import { apiClient } from "@/lib/api-client"

export async function listKnowledge() {
  const res = await apiClient.get("/v1/knowledge")
  return res.data as string[]
}

export async function uploadKnowledge(name: string, file: File) {
  const form = new FormData()
  form.append("file", file)
  const res = await apiClient.post(
    `/v1/knowledge/upload?name=${encodeURIComponent(name)}`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  )
  return res.data
}

export async function queryKnowledge(name: string, query: string) {
  const res = await apiClient.post(
    `/v1/knowledge/${name}/query?query=${encodeURIComponent(query)}`
  )
  return res.data
}
