import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"
import {
  Send,
  Copy,
  Check,
  Loader2,
  ChevronRight,
  Database,
  Settings2,
  ExternalLink,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import "katex/dist/katex.min.css"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { useQueryKnowledgeData } from "../hooks/use-knowledge-v2"
import type { QueryMode, QueryRequest, QueryReference } from "@/services/knowledge-v2"
import { apiClient } from "@/lib/api-client"

interface QueryPanelProps {
  knowledgeName: string
}

type MessageRole = "user" | "assistant"

interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  references?: QueryReference[]
  cot?: string
  isStreaming?: boolean
  timestamp: number
}

const QUERY_MODES: Array<{ value: QueryMode; label: string; desc: string }> = [
  { value: "local", label: "Local", desc: "Entity-centric retrieval" },
  { value: "global", label: "Global", desc: "Relation-centric retrieval" },
  { value: "hybrid", label: "Hybrid", desc: "Combined local + global" },
  { value: "naive", label: "Naive", desc: "Simple vector search" },
  { value: "mix", label: "Mix", desc: "Mixed strategy (default)" },
  { value: "bypass", label: "Bypass", desc: "Direct LLM, no retrieval" },
]

const RESPONSE_TYPES = [
  "Multiple Paragraphs",
  "Bullet Points",
  "Table",
  "Single Paragraph",
  "Short Answer",
]

interface QuerySettings {
  mode: QueryMode
  topK: number
  chunkTopK: number
  enableRerank: boolean
  includeReferences: boolean
  responseType: string
  userPrompt: string
}

const defaultSettings: QuerySettings = {
  mode: "mix",
  topK: 40,
  chunkTopK: 20,
  enableRerank: false,
  includeReferences: true,
  responseType: "Multiple Paragraphs",
  userPrompt: "",
}

let msgIdCounter = 0
function nextMsgId(): string {
  return `msg-${Date.now()}-${++msgIdCounter}`
}

export function QueryPanel({ knowledgeName }: QueryPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [settings, setSettings] = useState<QuerySettings>(defaultSettings)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const queryData = useQueryKnowledgeData()
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Auto-resize textarea
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  // Build the query request
  const buildRequest = useCallback(
    (queryText: string): QueryRequest => ({
      query: queryText,
      mode: settings.mode,
      top_k: settings.topK,
      chunk_top_k: settings.chunkTopK,
      enable_rerank: settings.enableRerank,
      include_references: settings.includeReferences,
      response_type: settings.responseType,
      user_prompt: settings.userPrompt || undefined,
      stream: true,
    }),
    [settings],
  )

  // Stream the query response
  const handleSend = useCallback(async () => {
    const queryText = input.trim()
    if (!queryText || isStreaming) return

    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: "user",
      content: queryText,
      timestamp: Date.now(),
    }

    const assistantId = nextMsgId()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput("")
    setIsStreaming(true)

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const baseURL = apiClient.defaults.baseURL || "/api"
      const url = `${baseURL}/v1/knowledge/${encodeURIComponent(knowledgeName)}/query/stream`
      const body = JSON.stringify(buildRequest(queryText))

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("No response body")

      const decoder = new TextDecoder()
      let buffer = ""
      let fullContent = ""
      let references: QueryReference[] | undefined

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const parsed = JSON.parse(line)
            if (parsed.error) {
              fullContent += `\n\n**Error:** ${parsed.error}`
            } else if (parsed.chunk) {
              fullContent += parsed.chunk
            } else if (parsed.response) {
              fullContent += parsed.response
            } else if (parsed.references) {
              references = parsed.references
            } else if (parsed.done) {
              // stream complete
            }
          } catch {
            // Skip malformed lines
          }
        }

        // Parse COT from content
        const cotMatch = fullContent.match(/<think>([\s\S]*?)<\/think>/)
        const cot = cotMatch ? cotMatch[1].trim() : undefined
        const displayContent = fullContent.replace(/<think>[\s\S]*?<\/think>/, "").trim()

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: displayContent, cot, references, isStreaming: true }
              : m,
          ),
        )
      }

      // Final update: mark as no longer streaming
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m,
        ),
      )
    } catch (error: unknown) {
      const errorMessage = error instanceof Error && error.name === "AbortError"
        ? "*Query cancelled.*"
        : `*Error: ${error instanceof Error ? error.message : "Unknown error"}*`

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: errorMessage, isStreaming: false }
            : m,
        ),
      )
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming, knowledgeName, buildRequest])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  // Handle "Get Data" request
  const handleGetData = useCallback(async () => {
    const queryText = input.trim()
    if (!queryText) return

    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: "user",
      content: `[Data Query] ${queryText}`,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg])

    try {
      const result = await queryData.mutateAsync({
        name: knowledgeName,
        request: buildRequest(queryText),
      })

      const assistantMsg: ChatMessage = {
        id: nextMsgId(),
        role: "assistant",
        content: `\`\`\`json\n${JSON.stringify(result.data, null, 2)}\n\`\`\``,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (error: unknown) {
      const assistantMsg: ChatMessage = {
        id: nextMsgId(),
        role: "assistant",
        content: `*Error: ${error instanceof Error ? error.message : "Failed to fetch data"}*`,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    }
  }, [input, knowledgeName, buildRequest, queryData])

  // Copy to clipboard
  const handleCopy = useCallback((id: string, content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }, [])

  // Render COT section
  const renderCot = (cot: string) => {
    return (
      <details className="mt-2 rounded-md border border-border/50 bg-muted/30">
        <summary className="flex cursor-pointer items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
          <ChevronRight className="h-3 w-3 transition-transform [[open]>&]:rotate-90" />
          Thinking Process
        </summary>
        <div className="border-t border-border/30 px-3 py-2 text-xs text-muted-foreground">
          {cot}
        </div>
      </details>
    )
  }

  return (
    <div className="flex h-[calc(100vh-240px)] min-h-[400px] flex-col">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
            <div className="text-center space-y-2">
              <Database className="mx-auto h-8 w-8 opacity-40" />
              <p>Ask a question about your knowledge base</p>
              <p className="text-xs opacity-60">
                Press Cmd+Enter to send
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex",
              msg.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[80%] rounded-lg px-4 py-3 text-sm",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground",
              )}
            >
              {/* COT section */}
              {msg.cot && renderCot(msg.cot)}

              {/* Main content */}
              {msg.role === "assistant" && msg.content ? (
                <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}

              {/* Streaming indicator */}
              {msg.isStreaming && !msg.content && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span className="text-xs">Generating...</span>
                </div>
              )}

              {/* References */}
              {msg.references && msg.references.length > 0 && (
                <div className="mt-3 border-t border-border/30 pt-2">
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    References
                  </p>
                  <div className="space-y-1">
                    {msg.references.map((ref, i) => (
                      <div
                        key={ref.reference_id || i}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground"
                      >
                        <ExternalLink className="h-3 w-3" />
                        <span className="truncate" title={ref.file_path}>
                          {ref.file_path || ref.reference_id}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Copy button for assistant messages */}
              {msg.role === "assistant" && msg.content && !msg.isStreaming && (
                <button
                  className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => handleCopy(msg.id, msg.content)}
                >
                  {copiedId === msg.id ? (
                    <>
                      <Check className="h-3 w-3" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      Copy
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="border-t p-4 space-y-3">
        {/* Advanced settings panel */}
        {showAdvanced && (
          <div className="rounded-lg border bg-muted/30 p-3 space-y-3">
            <div className="grid grid-cols-2 gap-4">
              {/* top_k */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">Top K (entities)</label>
                  <span className="text-xs tabular-nums text-muted-foreground">{settings.topK}</span>
                </div>
                <Slider
                  min={1}
                  max={100}
                  step={1}
                  value={[settings.topK]}
                  onValueChange={([v]) => setSettings((s) => ({ ...s, topK: v }))}
                />
              </div>

              {/* chunk_top_k */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">Chunk Top K</label>
                  <span className="text-xs tabular-nums text-muted-foreground">{settings.chunkTopK}</span>
                </div>
                <Slider
                  min={1}
                  max={50}
                  step={1}
                  value={[settings.chunkTopK]}
                  onValueChange={([v]) => setSettings((s) => ({ ...s, chunkTopK: v }))}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              {/* Rerank toggle */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={settings.enableRerank}
                  onCheckedChange={(v) => setSettings((s) => ({ ...s, enableRerank: v }))}
                />
                <label className="text-xs font-medium">Rerank</label>
              </div>

              {/* References toggle */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={settings.includeReferences}
                  onCheckedChange={(v) => setSettings((s) => ({ ...s, includeReferences: v }))}
                />
                <label className="text-xs font-medium">References</label>
              </div>

              {/* Response type */}
              <Select
                value={settings.responseType}
                onValueChange={(v) => setSettings((s) => ({ ...s, responseType: v }))}
              >
                <SelectTrigger className="w-[180px] h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RESPONSE_TYPES.map((rt) => (
                    <SelectItem key={rt} value={rt}>
                      {rt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* User prompt */}
            <div className="space-y-1">
              <label className="text-xs font-medium">Additional Prompt</label>
              <Textarea
                placeholder="Optional additional instructions..."
                value={settings.userPrompt}
                onChange={(e) => setSettings((s) => ({ ...s, userPrompt: e.target.value }))}
                className="min-h-[60px] text-xs"
              />
            </div>
          </div>
        )}

        {/* Main input row */}
        <div className="flex items-end gap-2">
          {/* Mode selector */}
          <Select
            value={settings.mode}
            onValueChange={(v) => setSettings((s) => ({ ...s, mode: v as QueryMode }))}
          >
            <SelectTrigger className="w-[120px] shrink-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {QUERY_MODES.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  <div>
                    <div className="font-medium">{m.label}</div>
                    <div className="text-xs text-muted-foreground">{m.desc}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Textarea */}
          <div className="flex-1 relative">
            <Textarea
              ref={textareaRef}
              placeholder="Ask a question..."
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              className="min-h-[40px] max-h-[200px] resize-none pr-10"
              rows={1}
              disabled={isStreaming}
            />
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={cn(showAdvanced && "bg-muted")}
              title="Advanced settings"
            >
              <Settings2 className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleGetData}
              disabled={!input.trim() || queryData.isPending}
              title="Get structured data"
            >
              {queryData.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Database className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="icon"
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
            >
              {isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
