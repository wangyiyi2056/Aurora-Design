import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  listKnowledge,
  uploadKnowledge,
  queryKnowledge,
} from "@/services/knowledge"

const queryKey = ["knowledge", "list"]

export function useKnowledgeList() {
  return useQuery({
    queryKey,
    queryFn: listKnowledge,
  })
}

export function useUploadKnowledge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) =>
      uploadKnowledge(name, file),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useQueryKnowledge() {
  return useMutation({
    mutationFn: ({ name, query }: { name: string; query: string }) =>
      queryKnowledge(name, query),
  })
}
