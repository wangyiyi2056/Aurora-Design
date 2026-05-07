import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  listKnowledge,
  uploadKnowledge,
  queryKnowledge,
  deleteKnowledge,
  deleteKnowledgeDocument,
  getKnowledgeDetail,
  listKnowledgeDocuments,
  type KnowledgeChunkConfig,
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
    mutationFn: ({
      name,
      file,
      chunkConfig,
    }: {
      name: string
      file: File
      chunkConfig?: KnowledgeChunkConfig
    }) => uploadKnowledge(name, file, chunkConfig),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useQueryKnowledge() {
  return useMutation({
    mutationFn: ({ name, query, topK }: { name: string; query: string; topK?: number }) =>
      queryKnowledge(name, query, topK),
  })
}

export function useKnowledgeDetail(name: string) {
  return useQuery({
    queryKey: ["knowledge", "detail", name],
    queryFn: () => getKnowledgeDetail(name),
    enabled: Boolean(name),
  })
}

export function useKnowledgeDocuments(name: string) {
  return useQuery({
    queryKey: ["knowledge", "documents", name],
    queryFn: () => listKnowledgeDocuments(name),
    enabled: Boolean(name),
  })
}

export function useDeleteKnowledge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteKnowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })
}

export function useDeleteKnowledgeDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, documentId }: { name: string; documentId: string }) =>
      deleteKnowledgeDocument(name, documentId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey })
      qc.invalidateQueries({ queryKey: ["knowledge", "documents", vars.name] })
      qc.invalidateQueries({ queryKey: ["knowledge", "detail", vars.name] })
    },
  })
}
