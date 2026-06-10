import { useCallback, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  X,
  FileText,
  Calendar,
  Hash,
  Layers,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Puzzle,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiClient } from "@/lib/api-client"
import type { DocStatusInfo } from "@/services/knowledge-v2"
import { StatusBadge } from "./StatusBadge"

interface DocumentPreviewProps {
  doc: DocStatusInfo | null
  knowledgeName: string
  onClose: () => void
}

interface ChunkData {
  id: string
  content: string
  chunk_order_index: number
  tokens: number
  file_path: string
  full_doc_id: string
}

async function fetchDocumentContent(
  knowledgeName: string,
  docId: string,
): Promise<{ content: string; content_type: string }> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(knowledgeName)}/documents/${encodeURIComponent(docId)}/content`,
  )
  return res.data
}

async function fetchDocumentChunks(
  knowledgeName: string,
  docId: string,
): Promise<{ chunks: ChunkData[]; total: number }> {
  const res = await apiClient.get(
    `/v1/knowledge/${encodeURIComponent(knowledgeName)}/documents/${encodeURIComponent(docId)}/chunks`,
  )
  return res.data
}

function ChunkItem({ chunk, index }: { chunk: ChunkData; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(chunk.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }, [chunk.content])

  // Show preview (first 200 chars)
  const preview =
    chunk.content.length > 200
      ? chunk.content.slice(0, 200) + "..."
      : chunk.content

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Chunk header */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <Badge variant="secondary" className="shrink-0 font-mono text-xs">
          #{index + 1}
        </Badge>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground/80 truncate">{preview}</p>
        </div>
        <div className="shrink-0 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{chunk.tokens} tokens</span>
          <span>{chunk.content.length} chars</span>
        </div>
      </button>

      {/* Chunk content (expanded) */}
      {expanded && (
        <div className="border-t bg-muted/20 px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground font-mono">
              {chunk.id}
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={handleCopy}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 mr-1" />
                  已复制
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  复制
                </>
              )}
            </Button>
          </div>
          <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/90 max-h-96 overflow-y-auto">
            {chunk.content}
          </pre>
        </div>
      )}
    </div>
  )
}

export function DocumentPreview({
  doc,
  knowledgeName,
  onClose,
}: DocumentPreviewProps) {
  const [activeTab, setActiveTab] = useState<"content" | "chunks">("content")
  const [showRaw, setShowRaw] = useState(false)

  const {
    data: contentData,
    isLoading: contentLoading,
    error: contentError,
  } = useQuery({
    queryKey: ["knowledge", knowledgeName, "doc-content", doc?.id],
    queryFn: () => fetchDocumentContent(knowledgeName, doc!.id),
    enabled: Boolean(doc) && activeTab === "content",
    staleTime: 60_000,
  })

  const {
    data: chunksData,
    isLoading: chunksLoading,
    error: chunksError,
  } = useQuery({
    queryKey: ["knowledge", knowledgeName, "doc-chunks", doc?.id],
    queryFn: () => fetchDocumentChunks(knowledgeName, doc!.id),
    enabled: Boolean(doc) && activeTab === "chunks",
    staleTime: 60_000,
  })

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    },
    [onClose],
  )

  if (!doc) return null

  const isMarkdown =
    doc.file_path.endsWith(".md") ||
    doc.file_path.endsWith(".mdx") ||
    contentData?.content_type === "markdown"

  return (
    <div
      className="fixed inset-0 z-50 flex"
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label="Document preview"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="relative ml-auto flex h-full w-full max-w-3xl flex-col bg-background shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center gap-3 border-b px-4 py-3 shrink-0">
          <FileText className="h-4 w-4 text-primary shrink-0" />
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold truncate">
              {doc.file_path.split("/").pop() || doc.file_path}
            </h3>
            <p className="text-xs text-muted-foreground truncate">
              {doc.file_path}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Metadata bar */}
        <div className="flex items-center gap-4 border-b px-4 py-2 text-xs text-muted-foreground shrink-0">
          <StatusBadge status={doc.status} />
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{new Date(doc.created_at).toLocaleDateString()}</span>
          </div>
          <div className="flex items-center gap-1">
            <Hash className="h-3 w-3" />
            <span>{doc.content_length.toLocaleString()} chars</span>
          </div>
          <div className="flex items-center gap-1">
            <Layers className="h-3 w-3" />
            <span>{doc.chunks_count} chunks</span>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex items-center border-b shrink-0">
          <button
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "content"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab("content")}
          >
            <FileText className="h-4 w-4" />
            文档内容
          </button>
          <button
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "chunks"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab("chunks")}
          >
            <Puzzle className="h-4 w-4" />
            Chunks
            {doc.chunks_count > 0 && (
              <Badge variant="secondary" className="text-xs h-5 px-1.5">
                {doc.chunks_count}
              </Badge>
            )}
          </button>
          {activeTab === "content" && (
            <div className="ml-auto pr-4 flex items-center gap-1">
              <Button
                variant={showRaw ? "default" : "ghost"}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowRaw(!showRaw)}
              >
                {showRaw ? "Markdown" : "Raw"}
              </Button>
            </div>
          )}
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {/* Content tab */}
          {activeTab === "content" && (
            <div className="px-6 py-4">
              {contentLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : contentError ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <AlertCircle className="h-8 w-8 text-destructive/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    无法加载文档内容
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {contentError instanceof Error
                      ? contentError.message
                      : "未知错误"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-3 max-w-sm">
                    提示：只有处理完成（PROCESSED）状态的文档才能查看内容。
                    如果文档仍在处理中或处理失败，请等待处理完成或检查错误信息。
                  </p>
                </div>
              ) : contentData?.content ? (
                showRaw ? (
                  <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/90">
                    {contentData.content}
                  </pre>
                ) : isMarkdown ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {contentData.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                    {contentData.content}
                  </pre>
                )
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="h-8 w-8 text-muted-foreground/30 mb-2" />
                  <p className="text-sm text-muted-foreground">无内容</p>
                  {doc.content_summary && (
                    <p className="text-xs text-muted-foreground mt-2 max-w-md">
                      {doc.content_summary}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Chunks tab */}
          {activeTab === "chunks" && (
            <div className="p-4">
              {chunksLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : chunksError ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <AlertCircle className="h-8 w-8 text-destructive/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    无法加载 Chunks
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {chunksError instanceof Error
                      ? chunksError.message
                      : "未知错误"}
                  </p>
                </div>
              ) : chunksData?.chunks && chunksData.chunks.length > 0 ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm text-muted-foreground">
                      文档被拆分为{" "}
                      <span className="font-semibold text-foreground">
                        {chunksData.total}
                      </span>{" "}
                      个 chunks
                    </p>
                  </div>
                  {chunksData.chunks.map((chunk, index) => (
                    <ChunkItem
                      key={chunk.id}
                      chunk={chunk}
                      index={index}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Puzzle className="h-8 w-8 text-muted-foreground/30 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    暂无 Chunks
                  </p>
                  <p className="text-xs text-muted-foreground mt-2 max-w-sm">
                    文档可能仍在处理中，或处理过程中未生成 chunks。
                    请检查文档状态是否为 PROCESSED。
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error message if any */}
        {doc.error_msg && (
          <div className="border-t bg-destructive/5 px-4 py-2 shrink-0">
            <p className="text-xs text-destructive flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              {doc.error_msg}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
