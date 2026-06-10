import { useTranslation } from "react-i18next"
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useMemo,
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
  Clock,
  Eraser,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
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
import { useQueryHistory, type HistoryEntry } from "../hooks/useQueryHistory"
import { QueryHistory } from "./QueryHistory"
import type { QueryMode, QueryRequest, QueryReference } from "@/services/knowledge-v2"
import { apiClient } from "@/lib/api-client"
import { useSettingsStore } from "../stores/settings"

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
  thinkingTime?: number | null
  isStreaming?: boolean
  isError?: boolean
  timestamp: number
}

const BYPASS_DEFAULT_HISTORY_TURNS = 3
const VALID_QUERY_MODES: QueryMode[] = ["naive", "local", "global", "hybrid", "mix", "bypass"]

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

let msgIdCounter = 0
function nextMsgId(): string {
  return `msg-${Date.now()}-${++msgIdCounter}`
}

function buildConversationHistory(
  messages: ChatMessage[],
  historyTurns: number,
): QueryRequest["conversation_history"] {
  if (historyTurns <= 0) return []

  return messages
    .filter(
      (message) =>
        message.role === "user" ||
        (message.role === "assistant" && !message.isError && !message.isStreaming),
    )
    .filter((message) => message.content.trim().length > 0)
    .slice(-historyTurns * 2)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }))
}

function parseQueryInput(input: string): { query: string; modeOverride?: QueryMode; error?: string } {
  const trimmed = input.trim()
  const prefixMatch = trimmed.match(/^\/(\w+)\s+([\s\S]+)/)

  if (/^\/\S+/.test(trimmed) && !prefixMatch) {
    return {
      query: trimmed,
      error: "Invalid query mode. Use /naive, /local, /global, /hybrid, /mix, or /bypass.",
    }
  }

  if (!prefixMatch) return { query: trimmed }

  const mode = prefixMatch[1] as QueryMode
  if (!VALID_QUERY_MODES.includes(mode)) {
    return {
      query: trimmed,
      error: "Invalid query mode. Use /naive, /local, /global, /hybrid, /mix, or /bypass.",
    }
  }

  return {
    query: prefixMatch[2].trim(),
    modeOverride: mode,
  }
}

function parseCotContent(content: string): { displayContent: string; cot?: string; isThinking: boolean } {
  const startTag = "<think>"
  const endTag = "</think>"
  const start = content.lastIndexOf(startTag)
  const end = content.lastIndexOf(endTag)

  if (start === -1) {
    return { displayContent: content.trim(), isThinking: false }
  }

  if (end === -1 || end < start) {
    return {
      displayContent: "",
      cot: content.slice(start + startTag.length).trim(),
      isThinking: true,
    }
  }

  return {
    displayContent: content.slice(end + endTag.length).trim(),
    cot: content.slice(start + startTag.length, end).trim(),
    isThinking: false,
  }
}

function toBackendQueryRequest(request: QueryRequest): QueryRequest {
  const { history_turns: _historyTurns, ...backendRequest } = request
  return backendRequest
}

/**
 * Render text with citation markers highlighted.
 * Citations appear as [1], [2], etc. or as inline file references.
 */
function HighlightedContent({
  content,
  references,
}: {
  content: string
  references?: QueryReference[]
}) {
  const highlightedContent = useMemo(() => {
    if (!references || references.length === 0) return null

    // Match citation patterns like [1], [2], [ref-1], etc.
    const citationPattern = /\[(\d+|ref-\d+|[\w-]+)\]/g
    const parts: Array<{ text: string; isCitation: boolean }> = []
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = citationPattern.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ text: content.slice(lastIndex, match.index), isCitation: false })
      }
      parts.push({ text: match[0], isCitation: true })
      lastIndex = match.index + match[0].length
    }
    if (lastIndex < content.length) {
      parts.push({ text: content.slice(lastIndex), isCitation: false })
    }

    return parts.length > 1 ? parts : null
  }, [content, references])

  if (!highlightedContent) return null

  return (
    <span>
      {highlightedContent.map((part, i) =>
        part.isCitation ? (
          <mark
            key={i}
            className="rounded bg-primary/15 px-0.5 text-primary font-medium not-italic"
          >
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </span>
  )
}

export function QueryPanel({ knowledgeName }: QueryPanelProps) {
  const { t } = useTranslation("construct")
  const querySettings = useSettingsStore.use.querySettings()
  const retrievalHistory = useSettingsStore.use.retrievalHistory()
  const setRetrievalHistory = useSettingsStore.use.setRetrievalHistory()
  const updateQuerySettings = useSettingsStore.use.updateQuerySettings()
  const addUserPromptToHistory = useSettingsStore.use.addUserPromptToHistory()
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    Array.isArray(retrievalHistory)
      ? retrievalHistory.map((message, index) => ({
          id: message.id || `hist-${Date.now()}-${index}`,
          role: message.role,
          content: message.content || "",
          references: message.references,
          cot: message.cot || message.thinkingContent,
          thinkingTime: message.thinkingTime ?? null,
          isError: message.isError,
          timestamp: message.timestamp || Date.now(),
        })).filter((message) => message.role === "user" || message.role === "assistant")
      : [],
  )
  const [input, setInput] = useState("")
  const [inputError, setInputError] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const queryData = useQueryKnowledgeData()
  const history = useQueryHistory()
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const thinkingStartRef = useRef<number | null>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Auto-resize textarea
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    if (inputError) setInputError("")
    const el = e.target
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [inputError])

  // Build the query request
  const buildRequest = useCallback(
    (
      queryText: string,
      mode: QueryMode,
      conversationHistory: QueryRequest["conversation_history"] = [],
    ): QueryRequest => ({
      query: queryText,
      mode,
      top_k: querySettings.top_k,
      chunk_top_k: querySettings.chunk_top_k,
      max_entity_tokens: querySettings.max_entity_tokens,
      max_relation_tokens: querySettings.max_relation_tokens,
      max_total_tokens: querySettings.max_total_tokens,
      only_need_context: querySettings.only_need_context,
      only_need_prompt: querySettings.only_need_prompt,
      enable_rerank: querySettings.enable_rerank,
      include_references: querySettings.include_references ?? true,
      response_type: querySettings.response_type || "Multiple Paragraphs",
      conversation_history: conversationHistory,
      user_prompt: querySettings.user_prompt || undefined,
      stream: querySettings.stream ?? true,
    }),
    [querySettings],
  )

  // Stream the query response
  const handleSend = useCallback(async () => {
    const rawInput = input.trim()
    if (!rawInput || isStreaming) return

    const parsedInput = parseQueryInput(rawInput)
    if (parsedInput.error) {
      setInputError(parsedInput.error)
      return
    }

    const queryText = parsedInput.query
    const effectiveMode = parsedInput.modeOverride || querySettings.mode || "mix"
    const configuredHistoryTurns = Number(querySettings.history_turns || 0)
    const effectiveHistoryTurns =
      effectiveMode === "bypass" && configuredHistoryTurns === 0
        ? BYPASS_DEFAULT_HISTORY_TURNS
        : configuredHistoryTurns
    const conversationHistory = buildConversationHistory(messages, effectiveHistoryTurns)

    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: "user",
      content: rawInput,
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

    const optimisticMessages = [...messages, userMsg, assistantMsg]
    setMessages(optimisticMessages)
    setInput("")
    setInputError("")
    setIsStreaming(true)
    thinkingStartRef.current = null

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const baseURL = apiClient.defaults.baseURL || "/api"
      const url = `${baseURL}/v1/knowledge/${encodeURIComponent(knowledgeName)}/query/stream`
      const body = JSON.stringify(
        toBackendQueryRequest(buildRequest(queryText, effectiveMode, conversationHistory)),
      )

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
      let hasError = false
      let thinkingTime: number | null = null

      const updateAssistant = () => {
        if (fullContent.includes("<think>") && !thinkingStartRef.current) {
          thinkingStartRef.current = Date.now()
        }
        const parsedCot = parseCotContent(fullContent)
        if (!parsedCot.isThinking && parsedCot.cot && thinkingStartRef.current && thinkingTime === null) {
          thinkingTime = (Date.now() - thinkingStartRef.current) / 1000
        }
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: parsedCot.displayContent,
                  cot: parsedCot.cot,
                  thinkingTime,
                  references,
                  isStreaming: true,
                  isError: hasError,
                }
              : m,
          ),
        )
      }

      const processLine = (line: string) => {
        if (!line.trim()) return
        try {
          const parsed = JSON.parse(line)
          if (parsed.error) {
            hasError = true
            references = undefined
            fullContent = fullContent
              ? `${fullContent}\n\nError: ${parsed.error}`
              : `Error: ${parsed.error}`
          }
          if (parsed.references && !hasError) {
            references = parsed.references
          }
          if (parsed.chunk) {
            fullContent += parsed.chunk
          }
          if (parsed.response) {
            fullContent += parsed.response
          }
          updateAssistant()
        } catch {
          // Skip malformed NDJSON fragments.
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          processLine(line)
        }
      }

      if (buffer.trim()) {
        processLine(buffer)
      }

      // Final update: mark as no longer streaming
      const finalCot = parseCotContent(fullContent)
      const finalAssistant: ChatMessage = {
        ...assistantMsg,
        content: finalCot.displayContent,
        cot: finalCot.cot,
        thinkingTime,
        references,
        isStreaming: false,
        isError: hasError,
      }
      const finalMessages = optimisticMessages.map((m) =>
        m.id === assistantId ? finalAssistant : m,
      )
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? finalAssistant : m,
        ),
      )

      // Save to query history
      if (!hasError && finalAssistant.content) {
        setRetrievalHistory(finalMessages)
        if (querySettings.user_prompt?.trim()) {
          addUserPromptToHistory(querySettings.user_prompt.trim())
        }
        history.addEntry({
          query: queryText,
          mode: effectiveMode,
          response: finalAssistant.content,
          referenceCount: references?.length ?? 0,
        })
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error && error.name === "AbortError"
        ? "Query cancelled."
        : `Error: ${error instanceof Error ? error.message : "Unknown error"}`

      const errorAssistant: ChatMessage = {
        ...assistantMsg,
        content: errorMessage,
        references: undefined,
        isStreaming: false,
        isError: true,
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? errorAssistant
            : m,
        ),
      )
    } finally {
      setIsStreaming(false)
      abortRef.current = null
      thinkingStartRef.current = null
    }
  }, [
    input,
    isStreaming,
    knowledgeName,
    buildRequest,
    messages,
    querySettings,
    history,
    setRetrievalHistory,
    addUserPromptToHistory,
  ])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  // Handle history entry selection — re-populate input and settings
  const handleHistorySelect = useCallback(
    (entry: HistoryEntry) => {
      setInput(entry.query)
      updateQuerySettings({ mode: entry.mode as QueryMode })
      setShowHistory(false)
      textareaRef.current?.focus()
    },
    [updateQuerySettings],
  )

  // Handle "Get Data" request
  const handleGetData = useCallback(async () => {
    const rawInput = input.trim()
    if (!rawInput) return
    const parsedInput = parseQueryInput(rawInput)
    if (parsedInput.error) {
      setInputError(parsedInput.error)
      return
    }

    const queryText = parsedInput.query
    const effectiveMode = parsedInput.modeOverride || querySettings.mode || "mix"

    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: "user",
      content: `[Data Query] ${rawInput}`,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg])

    try {
      const result = await queryData.mutateAsync({
        name: knowledgeName,
        request: toBackendQueryRequest(
          buildRequest(queryText, effectiveMode, buildConversationHistory(messages, 0)),
        ),
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
  }, [input, knowledgeName, buildRequest, queryData, messages, querySettings.mode])

  // Copy to clipboard
  const handleCopy = useCallback((id: string, content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }, [])

  const handleClearMessages = useCallback(() => {
    setMessages([])
    setRetrievalHistory([])
  }, [setRetrievalHistory])

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
    <div className="flex h-[calc(100vh-240px)] min-h-[400px]">
      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-w-0">
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
                Press Enter to send, Shift+Enter for a new line
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
                  {msg.references && msg.references.length > 0 ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        p: ({ children, ...props }) => {
                          const textContent = typeof children === "string"
                            ? children
                            : Array.isArray(children)
                              ? children.map((c) => (typeof c === "string" ? c : "")).join("")
                              : ""
                          const highlighted = (
                            <HighlightedContent
                              content={textContent}
                              references={msg.references}
                            />
                          )
                          return <p {...props}>{highlighted || children}</p>
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  )}
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
              {msg.references && msg.references.length > 0 && !msg.isError && (
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
              {msg.role === "assistant" && msg.content && !msg.isStreaming && !msg.isError && (
                <button
                  aria-label="Copy response"
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
                  <span className="text-xs tabular-nums text-muted-foreground">{querySettings.top_k ?? 40}</span>
                </div>
                <Slider
                  min={1}
                  max={100}
                  step={1}
                  value={[querySettings.top_k ?? 40]}
                  onValueChange={([v]) => updateQuerySettings({ top_k: v })}
                />
              </div>

              {/* chunk_top_k */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">Chunk Top K</label>
                  <span className="text-xs tabular-nums text-muted-foreground">{querySettings.chunk_top_k ?? 20}</span>
                </div>
                <Slider
                  min={1}
                  max={50}
                  step={1}
                  value={[querySettings.chunk_top_k ?? 20]}
                  onValueChange={([v]) => updateQuerySettings({ chunk_top_k: v })}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">History Turns</label>
                  <span className="text-xs tabular-nums text-muted-foreground">{querySettings.history_turns ?? 0}</span>
                </div>
                <Slider
                  min={0}
                  max={10}
                  step={1}
                  value={[querySettings.history_turns ?? 0]}
                  onValueChange={([v]) => updateQuerySettings({ history_turns: v })}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">Max Total Tokens</label>
                  <span className="text-xs tabular-nums text-muted-foreground">{querySettings.max_total_tokens ?? 30000}</span>
                </div>
                <Slider
                  min={1000}
                  max={60000}
                  step={1000}
                  value={[querySettings.max_total_tokens ?? 30000]}
                  onValueChange={([v]) => updateQuerySettings({ max_total_tokens: v })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium">Max Entity Tokens</label>
                <Textarea
                  value={String(querySettings.max_entity_tokens ?? 6000)}
                  onChange={(e) => updateQuerySettings({ max_entity_tokens: Number(e.target.value) || 6000 })}
                  className="min-h-8 h-8 text-xs"
                  rows={1}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Max Relation Tokens</label>
                <Textarea
                  value={String(querySettings.max_relation_tokens ?? 8000)}
                  onChange={(e) => updateQuerySettings({ max_relation_tokens: Number(e.target.value) || 8000 })}
                  className="min-h-8 h-8 text-xs"
                  rows={1}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              {/* Rerank toggle */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={Boolean(querySettings.enable_rerank)}
                  onCheckedChange={(v) => updateQuerySettings({ enable_rerank: v })}
                />
                <label className="text-xs font-medium">{t("knowledge.query.rerank")}</label>
              </div>

              {/* References toggle */}
              <div className="flex items-center gap-2">
                <Switch
                  checked={querySettings.include_references ?? true}
                  onCheckedChange={(v) => updateQuerySettings({ include_references: v })}
                />
                <label className="text-xs font-medium">{t("knowledge.query.references")}</label>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={querySettings.stream ?? true}
                  onCheckedChange={(v) => updateQuerySettings({ stream: v })}
                />
                <label className="text-xs font-medium">Stream</label>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={Boolean(querySettings.only_need_context)}
                  onCheckedChange={(v) =>
                    updateQuerySettings({
                      only_need_context: v,
                      only_need_prompt: v ? false : querySettings.only_need_prompt,
                    })
                  }
                />
                <label className="text-xs font-medium">Context Only</label>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={Boolean(querySettings.only_need_prompt)}
                  onCheckedChange={(v) =>
                    updateQuerySettings({
                      only_need_prompt: v,
                      only_need_context: v ? false : querySettings.only_need_context,
                    })
                  }
                />
                <label className="text-xs font-medium">Prompt Only</label>
              </div>

              {/* Response type */}
              <Select
                value={querySettings.response_type || "Multiple Paragraphs"}
                onValueChange={(v) => updateQuerySettings({ response_type: v })}
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
                value={querySettings.user_prompt || ""}
                onChange={(e) => updateQuerySettings({ user_prompt: e.target.value })}
                onBlur={() => {
                  if (querySettings.user_prompt?.trim()) {
                    addUserPromptToHistory(querySettings.user_prompt.trim())
                  }
                }}
                className="min-h-[60px] text-xs"
              />
            </div>
          </div>
        )}

        {/* Main input row */}
        <div className="flex items-end gap-2">
          {/* Mode selector */}
          <Select
            value={querySettings.mode || "mix"}
            onValueChange={(v) => updateQuerySettings({ mode: v as QueryMode })}
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
            {inputError && (
              <p className="absolute left-0 top-full mt-1 text-xs text-destructive">
                {inputError}
              </p>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClearMessages}
              disabled={isStreaming || messages.length === 0}
              title="Clear chat"
              aria-label="Clear chat"
            >
              <Eraser className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowHistory(!showHistory)}
              className={cn(showHistory && "bg-muted")}
              title={t("knowledge.query.history", "Query History")}
              aria-label={t("knowledge.query.history", "Query History")}
            >
              <Clock className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={cn(showAdvanced && "bg-muted")}
              title={t("knowledge.query.advancedSettings")}
              aria-label={t("knowledge.query.advancedSettings")}
            >
              <Settings2 className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleGetData}
              disabled={!input.trim() || queryData.isPending}
              title={t("knowledge.query.getStructuredData")}
              aria-label={t("knowledge.query.getStructuredData")}
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
              aria-label="Send query"
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

      {/* History sidebar */}
      {showHistory && (
        <div className="w-72 shrink-0 border-l overflow-hidden flex flex-col">
          <QueryHistory
            entries={history.entries}
            onSelect={handleHistorySelect}
            onRemove={history.removeEntry}
            onClearAll={history.clearAll}
            className="flex-1 min-h-0"
          />
        </div>
      )}
    </div>
  )
}
