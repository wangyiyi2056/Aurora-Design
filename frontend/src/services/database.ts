import { apiClient } from "@/lib/api-client"

export interface DatasourceConfig {
  name: string
  db_type: string
  database: string
  host?: string
  port?: number
  user?: string
  password?: string
  extra?: Record<string, unknown>
}

export interface DatasourceItem {
  name: string
  db_type: string
  connected: boolean
  tables?: string[]
  error?: string
}

export interface DatasourceDetail {
  name: string
  db_type: string
  config: DatasourceConfig
}

export async function listDatasources(): Promise<{ items: DatasourceItem[] }> {
  const res = await apiClient.get("/v1/datasource")
  return res.data as { items: DatasourceItem[] }
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

export async function testDatasource(name: string): Promise<DatasourceItem> {
  const res = await apiClient.post(`/v1/datasource/${encodeURIComponent(name)}/test`)
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

export async function runQuery(name: string, sql: string) {
  const res = await apiClient.post(`/v1/datasource/${encodeURIComponent(name)}/query`, { sql })
  return res.data
}
