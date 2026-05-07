import { apiClient } from "@/lib/api-client"

export async function listKnowledge() {
  const res = await apiClient.get("/v1/knowledge")
  return res.data as string[]
}

export interface KnowledgeDetail {
  name: string
  collection_name: string
  persist_directory: string
  chunks: number
  chunk_strategy: string
  chunk_size: number
  chunk_overlap: number
}

export interface KnowledgeDocument {
  id: string
  knowledge_name: string
  file_name: string
  file_path: string
  chunks: number
  created_at: number
  updated_at: number
}

export async function getKnowledgeDetail(name: string): Promise<KnowledgeDetail> {
  const res = await apiClient.get(`/v1/knowledge/${encodeURIComponent(name)}`)
  return res.data as KnowledgeDetail
}

export async function listKnowledgeDocuments(name: string): Promise<{ items: KnowledgeDocument[] }> {
  const res = await apiClient.get(`/v1/knowledge/${encodeURIComponent(name)}/documents`)
  return res.data as { items: KnowledgeDocument[] }
}

export async function deleteKnowledge(name: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/knowledge/${encodeURIComponent(name)}`)
  return res.data as { success: boolean }
}

export async function deleteKnowledgeDocument(
  name: string,
  documentId: string
): Promise<{ success: boolean }> {
  const res = await apiClient.delete(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/${encodeURIComponent(documentId)}`
  )
  return res.data as { success: boolean }
}

export interface KnowledgeChunkConfig {
  strategy: string
  size: number
  overlap: number
}

export async function uploadKnowledge(
  name: string,
  file: File,
  chunkConfig?: KnowledgeChunkConfig
) {
  const form = new FormData()
  form.append("file", file)
  const params = new URLSearchParams({ name })
  if (chunkConfig) {
    params.set("chunk_strategy", chunkConfig.strategy)
    params.set("chunk_size", String(chunkConfig.size))
    params.set("chunk_overlap", String(chunkConfig.overlap))
  }
  const res = await apiClient.post(
    `/v1/knowledge/upload?${params.toString()}`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  )
  return res.data
}

export async function queryKnowledge(name: string, query: string, topK?: number) {
  const params = new URLSearchParams({ query })
  if (topK) params.set("top_k", String(topK))
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/query?${params.toString()}`
  )
  return res.data
}
