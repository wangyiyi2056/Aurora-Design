import { apiClient } from "@/lib/api-client"

export interface DatasourceConfig {
  name: string
  db_type: string
  database: string
}

export interface DatasourceItem {
  name: string
  db_type: string
  connected: boolean
}

export async function listDatasources() {
  const res = await apiClient.get("/v1/datasource")
  return res.data as { items: DatasourceItem[] }
}

export async function createDatasource(config: DatasourceConfig) {
  const res = await apiClient.post("/v1/datasource", { config })
  return res.data
}

export async function runQuery(name: string, sql: string) {
  const res = await apiClient.post(`/v1/datasource/${name}/query`, { sql })
  return res.data
}
