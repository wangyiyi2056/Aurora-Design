import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  listDatasources,
  createDatasource,
  runQuery,
} from "@/services/database"

const queryKey = ["database", "datasources"]

export function useDatasources() {
  return useQuery({
    queryKey,
    queryFn: listDatasources,
  })
}

export function useCreateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createDatasource,
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useRunQuery() {
  return useMutation({
    mutationFn: ({ name, sql }: { name: string; sql: string }) =>
      runQuery(name, sql),
  })
}
