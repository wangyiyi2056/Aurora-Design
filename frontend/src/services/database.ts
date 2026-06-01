import { apiClient } from "@/lib/api-client"

// ── Types ──────────────────────────────────────────────────────────

export interface DatasourceConfig {
  name: string
  db_type: string
  database?: string
  host?: string
  port?: number
  user?: string
  password?: string
  description?: string
  extra?: Record<string, unknown>
}

export interface DatasourceItem {
  name: string
  db_type: string
  description: string
  connected: boolean
  tables?: string[]
  error?: string
  created_at?: number
  updated_at?: number
}

export interface DatasourceDetail {
  name: string
  db_type: string
  description: string
  config: DatasourceConfig
  created_at?: number
  updated_at?: number
}

export interface ParameterDefinition {
  name: string
  label: string
  type: string
  required: boolean
  default?: unknown
  description: string
  placeholder: string
}

export interface DatasourceTypeInfo {
  name: string
  label: string
  description: string
  icon: string
  is_file_db: boolean
  parameters: ParameterDefinition[]
}

export interface DatasourceTypesResponse {
  types: DatasourceTypeInfo[]
}

export interface DatabaseSummary {
  name: string
  db_type: string
  tables: Record<string, unknown>
  relationships: Array<Record<string, unknown>>
}

export interface QueryResult {
  success: boolean
  result: unknown
  error?: string
}

// ── API functions ──────────────────────────────────────────────────

export async function listDatasources(): Promise<{ items: DatasourceItem[] }> {
  const res = await apiClient.get("/v1/datasource")
  return res.data as { items: DatasourceItem[] }
}

export async function getDatasourceTypes(): Promise<DatasourceTypesResponse> {
  const res = await apiClient.get("/v1/datasource/types")
  return res.data
}

export async function createDatasource(config: DatasourceConfig): Promise<DatasourceItem> {
  const res = await apiClient.post("/v1/datasource", { config })
  return res.data
}

export async function getDatasource(name: string): Promise<DatasourceDetail> {
  const res = await apiClient.get(`/v1/datasource/${encodeURIComponent(name)}`)
  return res.data
}

export async function updateDatasource(
  name: string,
  config: DatasourceConfig
): Promise<DatasourceItem> {
  const res = await apiClient.put(`/v1/datasource/${encodeURIComponent(name)}`, { config })
  return res.data
}

export async function deleteDatasource(name: string): Promise<{ success: boolean }> {
  const res = await apiClient.delete(`/v1/datasource/${encodeURIComponent(name)}`)
  return res.data
}

export async function testDatasourceByName(name: string): Promise<DatasourceItem> {
  const res = await apiClient.post(`/v1/datasource/${encodeURIComponent(name)}/test`)
  return res.data
}

export async function testDatasourceConnection(config: DatasourceConfig): Promise<DatasourceItem> {
  const res = await apiClient.post("/v1/datasource/test-connection", config)
  return res.data
}

export async function refreshDatasource(name: string): Promise<{ success: boolean }> {
  const res = await apiClient.post(`/v1/datasource/${encodeURIComponent(name)}/refresh`)
  return res.data
}

export async function getDatasourceSummary(name: string): Promise<DatabaseSummary> {
  const res = await apiClient.get(`/v1/datasource/${encodeURIComponent(name)}/summary`)
  return res.data
}

export async function listDatasourceTables(name: string): Promise<{ tables: string[] }> {
  const res = await apiClient.get(`/v1/datasource/${encodeURIComponent(name)}/tables`)
  return res.data
}

export async function getDatasourceTableSchema(
  name: string,
  table: string
): Promise<{ name: string; schema_ddl: string }> {
  const res = await apiClient.get(
    `/v1/datasource/${encodeURIComponent(name)}/schema/${encodeURIComponent(table)}`
  )
  return res.data
}

export async function runQuery(name: string, sql: string): Promise<QueryResult> {
  const res = await apiClient.post(`/v1/datasource/${encodeURIComponent(name)}/query`, { sql })
  return res.data
}

// ── Saved Queries ────────────────────────────────────────────────

export interface SavedQuery {
  id: string
  datasource_name: string
  sql: string
  description: string
  created_at?: number
  updated_at?: number
}

export interface SavedQueryCreate {
  datasource_name: string
  sql: string
  description: string
}

export interface SavedQueryUpdate {
  sql?: string
  description?: string
}

export async function listSavedQueries(
  datasourceName: string
): Promise<{ items: SavedQuery[] }> {
  const res = await apiClient.get(
    `/v1/datasource/saved-queries/${encodeURIComponent(datasourceName)}`
  )
  return res.data as { items: SavedQuery[] }
}

export async function saveQuery(data: SavedQueryCreate): Promise<SavedQuery> {
  const res = await apiClient.post("/v1/datasource/saved-queries", data)
  return res.data as SavedQuery
}

export async function updateSavedQuery(
  queryId: string,
  data: SavedQueryUpdate
): Promise<SavedQuery> {
  const res = await apiClient.put(
    `/v1/datasource/saved-queries/${encodeURIComponent(queryId)}`,
    data
  )
  return res.data as SavedQuery
}

export async function deleteSavedQuery(
  queryId: string
): Promise<{ success: boolean }> {
  const res = await apiClient.delete(
    `/v1/datasource/saved-queries/${encodeURIComponent(queryId)}`
  )
  return res.data as { success: boolean }
}
