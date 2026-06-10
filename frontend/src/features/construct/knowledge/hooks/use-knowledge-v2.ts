import { useQuery, useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query"
import {
  listKnowledgeV2,
  uploadDocument,
  insertText,
  getDocumentsPaginated,
  getStatusCounts,
  getPipelineStatus,
  deleteDocuments,
  getCacheStats,
  clearCache,
  reprocessFailed,
  cancelPipeline,
  diagnoseDocuments,
  repairDocuments,
  queryKnowledgeV2,
  queryKnowledgeData,
  getGraphLabels,
  getSubgraph,
  getPopularLabels,
  searchLabels,
  updateEntity,
  createEntity,
  deleteEntity,
  updateRelation,
  createRelation,
  mergeEntities,
  type DocumentsRequest,
  type QueryRequest,
  type EntityUpdateRequest,
  type EntityCreateRequest,
  type RelationCreateRequest,
  type EntityMergeRequest,
} from "@/services/knowledge-v2"
import { getKnowledgeDetail as getV1Detail } from "@/services/knowledge"

// ─────────────────────────────────────────────────────────────────────────────
// Query key factories
// ─────────────────────────────────────────────────────────────────────────────

export const knowledgeKeys = {
  all: ["knowledge", "v2"] as const,
  list: () => [...knowledgeKeys.all, "list"] as const,
  detail: (name: string) => [...knowledgeKeys.all, "detail", name] as const,
  documents: (name: string) => [...knowledgeKeys.all, "documents", name] as const,
  documentsPaginated: (name: string, params: DocumentsRequest) =>
    [...knowledgeKeys.all, "documents", name, "paginated", params] as const,
  statusCounts: (name: string) => [...knowledgeKeys.all, "status-counts", name] as const,
  pipeline: (name: string) => [...knowledgeKeys.all, "pipeline-status", name] as const,
  cacheStats: (name: string) => [...knowledgeKeys.all, "cache-stats", name] as const,
  graph: (name: string) => [...knowledgeKeys.all, "graph", name] as const,
  graphLabels: (name: string) => [...knowledgeKeys.all, "graph", name, "labels"] as const,
  popularLabels: (name: string, limit: number) =>
    [...knowledgeKeys.all, "graph", "popular-labels", name, limit] as const,
  searchLabels: (name: string, q: string, limit: number) =>
    [...knowledgeKeys.all, "graph", "search-labels", name, q, limit] as const,
  subgraph: (name: string, label: string, depth: number, nodes: number) =>
    [...knowledgeKeys.all, "graph", "subgraph", name, label, depth, nodes] as const,
}

export function invalidateKnowledgeDetailV2Queries(qc: QueryClient, name: string) {
  qc.invalidateQueries({ queryKey: knowledgeKeys.detail(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.cacheStats(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
  qc.invalidateQueries({ queryKey: knowledgeKeys.graphLabels(name) })
  qc.invalidateQueries({
    predicate: (query) => {
      const key = query.queryKey
      if (key[0] !== "knowledge" || key[1] !== "v2" || key[2] !== "graph") return false
      return key[3] === name || key[4] === name
    },
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Knowledge list
// ─────────────────────────────────────────────────────────────────────────────

export function useKnowledgeListV2() {
  return useQuery({
    queryKey: knowledgeKeys.list(),
    queryFn: listKnowledgeV2,
  })
}

export function useKnowledgeDetailV2(name: string) {
  return useQuery({
    queryKey: knowledgeKeys.detail(name),
    queryFn: () => getV1Detail(name),
    enabled: Boolean(name),
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Document queries
// ─────────────────────────────────────────────────────────────────────────────

// Statuses indicating a document is actively being processed
const ACTIVE_STATUSES = new Set(["PARSING", "ANALYZING", "PREPROCESSED", "PROCESSING", "PENDING"])

function hasActiveDocuments(data: unknown): boolean {
  if (!data || typeof data !== "object") return false
  const items = (data as { items?: Array<{ status?: string }> }).items
  if (!Array.isArray(items)) return false
  return items.some((d) => d.status && ACTIVE_STATUSES.has(d.status))
}

export function useDocumentsPaginated(name: string, params: DocumentsRequest) {
  return useQuery({
    queryKey: knowledgeKeys.documentsPaginated(name, params),
    queryFn: () => getDocumentsPaginated(name, params),
    enabled: Boolean(name),
    refetchInterval: (query) => {
      // Fast poll when documents are being processed, slow when idle
      return hasActiveDocuments(query.state.data) ? 2000 : 30000
    },
  })
}

/** @deprecated Use `useDocumentsPaginated` instead. */
export const useKnowledgeDocumentsV2 = useDocumentsPaginated

export function useStatusCounts(name: string) {
  return useQuery({
    queryKey: knowledgeKeys.statusCounts(name),
    queryFn: () => getStatusCounts(name),
    enabled: Boolean(name),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data?.counts) return 30000
      const hasActive = Object.entries(data.counts).some(
        ([status, count]) => ACTIVE_STATUSES.has(status) && count > 0,
      )
      return hasActive ? 3000 : 30000
    },
  })
}

export function usePipelineStatus(name: string, enabled = true) {
  return useQuery({
    queryKey: knowledgeKeys.pipeline(name),
    queryFn: () => getPipelineStatus(name),
    enabled: Boolean(name) && enabled,
    refetchInterval: (query) => {
      const busy = (query.state.data as { busy?: boolean })?.busy ?? false
      return busy ? 1500 : 15000
    },
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Document mutations
// ─────────────────────────────────────────────────────────────────────────────

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) =>
      uploadDocument(name, file),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.detail(name) })
    },
  })
}

export function useInsertText() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      name,
      text,
      fileSource,
    }: {
      name: string
      text: string
      fileSource?: string
    }) => insertText(name, { text, file_source: fileSource }),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
    },
  })
}

export function useDeleteDocuments() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      name,
      docIds,
      deleteFile = false,
      deleteLlmCache = false,
      force = false,
    }: {
      name: string
      docIds: string[]
      deleteFile?: boolean
      deleteLlmCache?: boolean
      force?: boolean
    }) =>
      deleteDocuments(name, {
        doc_ids: docIds,
        delete_file: deleteFile,
        delete_llm_cache: deleteLlmCache,
        force,
      }),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.detail(name) })
    },
  })
}

export function useReprocessFailed() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name }: { name: string }) => reprocessFailed(name),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
    },
  })
}

export function useCancelPipeline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name }: { name: string }) => cancelPipeline(name),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
    },
  })
}

export function useClearCache() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name }: { name: string }) => clearCache(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useCacheStats(name: string) {
  return useQuery({
    queryKey: knowledgeKeys.cacheStats(name),
    queryFn: () => getCacheStats(name),
    enabled: !!name,
    refetchOnWindowFocus: false,
  })
}

export function useDiagnoseDocuments() {
  return useQuery({
    queryKey: ["knowledge", "v2", "diagnose"],
    queryFn: () => diagnoseDocuments(""),
    enabled: false,
  })
}

export function useRepairDocuments() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name }: { name: string }) => repairDocuments(name),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.documents(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.statusCounts(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.pipeline(name) })
    },
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Query mutations
// ─────────────────────────────────────────────────────────────────────────────

export function useRagQuery() {
  return useMutation({
    mutationFn: ({ name, request }: { name: string; request: QueryRequest }) =>
      queryKnowledgeV2(name, request),
  })
}

/** @deprecated Use `useRagQuery` instead. */
export const useQueryKnowledgeV2 = useRagQuery

export function useQueryData() {
  return useMutation({
    mutationFn: ({ name, request }: { name: string; request: QueryRequest }) =>
      queryKnowledgeData(name, request),
  })
}

/** @deprecated Use `useQueryData` instead. */
export const useQueryKnowledgeData = useQueryData

// ─────────────────────────────────────────────────────────────────────────────
// Graph queries
// ─────────────────────────────────────────────────────────────────────────────


export function useGraphLabels(name: string) {
  return useQuery({
    queryKey: knowledgeKeys.graphLabels(name),
    queryFn: () => getGraphLabels(name),
    enabled: Boolean(name),
  })
}

export function useSubgraph(name: string, label: string, maxDepth = 3, maxNodes = 1000) {
  return useQuery({
    queryKey: knowledgeKeys.subgraph(name, label, maxDepth, maxNodes),
    queryFn: () => getSubgraph(name, label, maxDepth, maxNodes),
    enabled: Boolean(name) && Boolean(label),
  })
}

/** @deprecated Use `useSubgraph` instead. */
export const useGraphSubgraph = useSubgraph

export function usePopularLabels(name: string, limit = 300) {
  return useQuery({
    queryKey: knowledgeKeys.popularLabels(name, limit),
    queryFn: () => getPopularLabels(name, limit),
    enabled: Boolean(name),
  })
}

export function useSearchLabels(name: string, q: string, limit = 50) {
  return useQuery({
    queryKey: knowledgeKeys.searchLabels(name, q, limit),
    queryFn: () => searchLabels(name, q, limit),
    enabled: Boolean(name) && q.length > 0,
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph mutations
// ─────────────────────────────────────────────────────────────────────────────

export function useUpdateEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: EntityUpdateRequest }) =>
      updateEntity(name, data),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.graphLabels(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useCreateEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: EntityCreateRequest }) =>
      createEntity(name, data),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.graphLabels(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useDeleteEntity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, entityId }: { name: string; entityId: string }) =>
      deleteEntity(name, entityId),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.graphLabels(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useUpdateRelation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string
      data: { source_entity: string; target_entity: string; updated_data: Record<string, unknown> }
    }) => updateRelation(name, data),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useCreateRelation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: RelationCreateRequest }) =>
      createRelation(name, data),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

export function useMergeEntities() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: EntityMergeRequest }) =>
      mergeEntities(name, data),
    onSuccess: (_data, { name }) => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.graph(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.graphLabels(name) })
      qc.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}
