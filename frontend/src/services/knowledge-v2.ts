import { apiClient } from "@/lib/api-client"

// ─────────────────────────────────────────────────────────────────────────────
// Query types
// ─────────────────────────────────────────────────────────────────────────────

export type QueryMode = "local" | "global" | "hybrid" | "naive" | "mix" | "bypass"

export interface QueryRequest {
  query: string
  mode: QueryMode
  only_need_context?: boolean
  only_need_prompt?: boolean
  response_type?: string
  top_k?: number
  chunk_top_k?: number
  max_entity_tokens?: number
  max_relation_tokens?: number
  max_total_tokens?: number
  hl_keywords?: string[]
  ll_keywords?: string[]
  conversation_history?: Array<{ role: string; content: string }>
  user_prompt?: string
  enable_rerank?: boolean
  include_references?: boolean
  include_chunk_content?: boolean
  stream?: boolean
}

export interface QueryReference {
  reference_id: string
  file_path: string
}

export interface QueryResponse {
  response: string
  references?: QueryReference[]
}

export interface QueryDataResponse {
  status: string
  message: string
  data: {
    entities: Array<Record<string, unknown>>
    relationships: Array<Record<string, unknown>>
    chunks: Array<Record<string, unknown>>
    references: QueryReference[]
  }
  metadata: {
    query_mode: string
    keywords: { high_level: string[]; low_level: string[] }
    processing_info: Record<string, number>
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Document types
// ─────────────────────────────────────────────────────────────────────────────

export type DocStatus =
  | "PENDING"
  | "PARSING"
  | "ANALYZING"
  | "PREPROCESSED"
  | "PROCESSING"
  | "PROCESSED"
  | "FAILED"

export interface DocStatusInfo {
  id: string
  file_path: string
  status: DocStatus
  content_summary: string
  content_length: number
  chunks_count: number
  error_msg: string | null
  track_id: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PipelineStatus {
  busy: boolean
  job_name: string
  job_start: string
  docs: { total: number; processed: number; failed: number; pending: number }
  stages: { parsing: number; processing: number }
  batches: { total: number; current: number }
  cur_batch: number
  request_pending: boolean
  latest_message: string
  history_messages: string[]
  update_status: string
}

export interface DocumentsRequest {
  status_filter?: DocStatus
  status_filters?: DocStatus[]
  page?: number
  page_size?: number
  sort_field?: string
  sort_direction?: "asc" | "desc"
}

export interface DocumentsPaginatedResponse {
  items: DocStatusInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface StatusCountsResponse {
  counts: Record<DocStatus, number>
  total: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph types
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string
  entity_name?: string
  entity_type?: string
  description?: string
  weight?: number
  [key: string]: unknown
}

export interface GraphEdge {
  source_id: string
  target_id: string
  description?: string
  keywords?: string
  weight?: number
  [key: string]: unknown
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface EntityUpdateRequest {
  entity_name: string
  updated_data: Record<string, unknown>
  allow_rename?: boolean
  allow_merge?: boolean
}

export interface EntityCreateRequest {
  entity_name: string
  entity_type: string
  description: string
}

export interface RelationCreateRequest {
  source_entity: string
  target_entity: string
  relation_data: Record<string, unknown>
}

export interface EntityMergeRequest {
  entities_to_change: string[]
  entity_to_change_into: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Knowledge management
// ─────────────────────────────────────────────────────────────────────────────

export async function listKnowledgeV2(): Promise<string[]> {
  const res = await apiClient.get("/v1/knowledge")
  return res.data as string[]
}

// ─────────────────────────────────────────────────────────────────────────────
// Documents
// ─────────────────────────────────────────────────────────────────────────────

export async function uploadDocument(name: string, file: File) {
  const formData = new FormData()
  formData.append("file", file)
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  )
  return res.data
}

export async function insertText(
  name: string,
  data: { text: string; file_source?: string }
) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/text`,
    data
  )
  return res.data
}

export async function insertTexts(
  name: string,
  data: { texts: string[]; file_sources?: string[] }
) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/texts`,
    data
  )
  return res.data
}

export async function scanDocuments(name: string) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/scan`
  )
  return res.data
}

export async function getDocumentsPaginated(
  name: string,
  params: DocumentsRequest
): Promise<DocumentsPaginatedResponse> {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/paginated`,
    params
  )
  return res.data as DocumentsPaginatedResponse
}

export async function getStatusCounts(name: string): Promise<StatusCountsResponse> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/status_counts`
  )
  return res.data as StatusCountsResponse
}

export async function getPipelineStatus(name: string): Promise<PipelineStatus> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/pipeline_status`
  )
  return res.data as PipelineStatus
}

export async function getTrackStatus(name: string, trackId: string) {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/track/${encodeURIComponent(trackId)}`
  )
  return res.data
}

export async function deleteDocuments(
  name: string,
  data: {
    doc_ids: string[]
    delete_file?: boolean
    delete_llm_cache?: boolean
    force?: boolean
  }
) {
  const res = await apiClient.delete(
    `/v1/knowledge/${encodeURIComponent(name)}/documents`,
    { data }
  )
  return res.data
}

export async function clearCache(name: string) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/clear_cache`
  )
  return res.data
}

export async function reprocessFailed(name: string) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/reprocess_failed`
  )
  return res.data
}

export async function cancelPipeline(name: string) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/documents/cancel_pipeline`
  )
  return res.data
}

// ─────────────────────────────────────────────────────────────────────────────
// Query
// ─────────────────────────────────────────────────────────────────────────────

export async function queryKnowledgeV2(
  name: string,
  data: QueryRequest
): Promise<QueryResponse> {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/query`,
    data
  )
  return res.data as QueryResponse
}

export async function queryKnowledgeData(
  name: string,
  data: QueryRequest
): Promise<QueryDataResponse> {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/query/data`,
    data
  )
  return res.data as QueryDataResponse
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph
// ─────────────────────────────────────────────────────────────────────────────


export async function getGraphLabels(name: string): Promise<string[]> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/labels`
  )
  return res.data as string[]
}

export async function getPopularLabels(name: string, limit = 300): Promise<string[]> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/labels/popular`,
    { params: { limit } }
  )
  return res.data as string[]
}

export async function searchLabels(name: string, q: string, limit = 50): Promise<string[]> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/labels/search`,
    { params: { q, limit } }
  )
  return res.data as string[]
}

export async function getSubgraph(
  name: string,
  label: string,
  maxDepth = 3,
  maxNodes = 1000
): Promise<GraphData> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/subgraph`,
    { params: { label, max_depth: maxDepth, max_nodes: maxNodes } }
  )
  return res.data as GraphData
}

export async function checkEntityExists(name: string, entityName: string) {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/entity/exists`,
    { params: { entity_name: entityName } }
  )
  return res.data
}

export async function updateEntity(name: string, data: EntityUpdateRequest) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/entity/edit`,
    data
  )
  return res.data
}

export async function createEntity(name: string, data: EntityCreateRequest) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/entity/create`,
    data
  )
  return res.data
}

export async function updateRelation(
  name: string,
  data: { source_entity: string; target_entity: string; updated_data: Record<string, unknown> }
) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/relation/edit`,
    data
  )
  return res.data
}

export async function createRelation(name: string, data: RelationCreateRequest) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/relation/create`,
    data
  )
  return res.data
}

export async function mergeEntities(name: string, data: EntityMergeRequest) {
  const res = await apiClient.post(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/entities/merge`,
    data
  )
  return res.data
}

export async function deleteEntity(name: string, entityId: string) {
  const res = await apiClient.delete(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/entity/${encodeURIComponent(entityId)}`
  )
  return res.data
}

export async function deleteRelation(name: string, sourceId: string, targetId: string) {
  const res = await apiClient.delete(
    `/v1/knowledge/${encodeURIComponent(name)}/graph/relation`,
    { params: { source_id: sourceId, target_id: targetId } }
  )
  return res.data
}
