import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  listDatasources,
  getDatasourceTypes,
  createDatasource,
  updateDatasource,
  deleteDatasource,
  testDatasourceConnection,
  refreshDatasource,
  getDatasourceSummary,
  listDatasourceTables,
  runQuery,
  listSavedQueries,
  saveQuery,
  updateSavedQuery,
  deleteSavedQuery,
  type DatasourceConfig,
  type SavedQueryCreate,
  type SavedQueryUpdate,
} from "@/services/database"

const queryKey = ["database", "datasources"]
const typesKey = ["database", "types"]

export function useDatasources() {
  return useQuery({
    queryKey,
    queryFn: listDatasources,
  })
}

export function useDatasourceTypes() {
  return useQuery({
    queryKey: typesKey,
    queryFn: getDatasourceTypes,
    staleTime: 1000 * 60 * 30,
  })
}

export function useCreateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createDatasource,
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useUpdateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, config }: { name: string; config: DatasourceConfig }) =>
      updateDatasource(name, config),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useDeleteDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteDatasource,
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useTestConnection() {
  return useMutation({
    mutationFn: testDatasourceConnection,
  })
}

export function useRefreshDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: refreshDatasource,
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useDatasourceSummary(name: string | null) {
  return useQuery({
    queryKey: ["database", "summary", name],
    queryFn: () => getDatasourceSummary(name!),
    enabled: !!name,
  })
}

export function useDatasourceTables(name: string | null) {
  return useQuery({
    queryKey: ["database", "tables", name],
    queryFn: () => listDatasourceTables(name!),
    enabled: !!name,
  })
}

export function useRunQuery() {
  return useMutation({
    mutationFn: ({ name, sql }: { name: string; sql: string }) =>
      runQuery(name, sql),
  })
}

// ── Saved Queries ───────────────────────────────────────────────

const savedQueriesKey = (name: string | null) => ["database", "saved-queries", name]

export function useSavedQueries(name: string | null) {
  return useQuery({
    queryKey: savedQueriesKey(name),
    queryFn: () => listSavedQueries(name!),
    enabled: !!name,
    staleTime: 1000 * 60 * 5,
  })
}

export function useSaveQuery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: SavedQueryCreate) => saveQuery(data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: savedQueriesKey(variables.datasource_name) })
    },
  })
}

export function useUpdateSavedQuery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ queryId, data }: { queryId: string; data: SavedQueryUpdate }) =>
      updateSavedQuery(queryId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["database", "saved-queries"] })
    },
  })
}

export function useDeleteSavedQuery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (queryId: string) => deleteSavedQuery(queryId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["database", "saved-queries"] })
    },
  })
}
