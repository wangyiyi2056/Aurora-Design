import { useState, Suspense, lazy, Component, type ReactNode } from "react"
import { User, Bot, Check, Copy } from "lucide-react"
import { useTranslation } from "react-i18next"
import { cn } from "@/lib/utils"
import type { MessagePart, ToolPart, ReasoningPart } from "@/stores/chat-store"
import { ToolCard } from "./tool-card"
import { ReasoningDisplay } from "./reasoning-display"
import { exactDateTime, relativeTimeLong } from "../utils/chat-time"
import { unfinishedTodosFromToolInput } from "../runtime/todos"

const MessageRenderer = lazy(() => import("./message-renderer"))

/**
 * Simple ErrorBoundary for lazy-loaded components.
 * Catches rendering errors and displays a fallback message.
 */
class MessageRendererErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <span className="text-muted-foreground text-xs">
          Failed to render message content
        </span>
      )
    }
    return this.props.children
  }
}

interface ChatMessageItemProps {
  role: "user" | "assistant" | "system"
  content: string | MessagePart[]
  /** Start time for reasoning duration display */
  startTime?: number
  /** End time for reasoning duration display */
  endTime?: number
  /** Additional thinking content (legacy prop for backward compatibility) */
  thinkingContent?: string
  /** Whether this message is currently streaming */
  streaming?: boolean
}

// Helper to get text content from MessagePart[]
function getTextContent(content: string | MessagePart[]): string {
  if (typeof content === "string") return content
  return content.filter(p => p.type === "text").map(p => (p as { text: string }).text).join("")
}

// Helper to get tool parts from MessagePart[]
function getToolParts(content: string | MessagePart[]): ToolPart[] {
  if (typeof content === "string") return []
  return content.filter(p => p.type === "tool") as ToolPart[]
}

// Helper to get reasoning parts from MessagePart[]
function getReasoningParts(content: string | MessagePart[]): ReasoningPart[] {
  if (typeof content === "string") return []
  return content.filter(p => p.type === "reasoning") as ReasoningPart[]
}

export function ChatMessageItem({
  role,
  content,
  startTime,
  endTime,
  thinkingContent,
  streaming = false,
}: ChatMessageItemProps) {
  const isUser = role === "user"
  const [copied, setCopied] = useState(false)
  const { t } = useTranslation("chat")

  // Get string content for display/copy
  const textContent = getTextContent(content)
  // Get tool and reasoning parts
  const toolParts = getToolParts(content)
  const reasoningParts = getReasoningParts(content)
  // Has multi-part content
  const hasToolParts = toolParts.length > 0
  const hasReasoningParts = reasoningParts.length > 0 || !!thinkingContent
  // Combined reasoning content
  const combinedReasoning = reasoningParts.map(p => p.text).join("\n") || thinkingContent || ""
  const unfinishedTodos = toolParts
    .filter((part) => part.tool.toLowerCase() === "todowrite")
    .flatMap((part) => unfinishedTodosFromToolInput(part.state.input))
  const timestamp = startTime ?? endTime

  if (role === "system") {
    return (
      <div className="text-center text-muted-foreground/50 text-[11px] py-2 tracking-wide uppercase">
        {textContent}
      </div>
    )
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(textContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div
      className={cn(
        "flex gap-3 group animate-message-fade-in",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] text-sm",
          isUser
            ? "gradient-avatar text-white shadow-lg shadow-blue-500/25 ring-1 ring-white/20"
            : "bg-muted/50 text-muted-foreground border border-border/40 ring-1 ring-white/[0.03]"
        )}
        aria-hidden="true"
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div className="relative max-w-[80%] flex flex-col">
        {!isUser && timestamp && (
          <time
            className="mb-1 text-[11px] text-muted-foreground/50"
            dateTime={new Date(timestamp).toISOString()}
            title={exactDateTime(timestamp)}
          >
            {relativeTimeLong(timestamp)}
          </time>
        )}

        {/* Reasoning parts - displayed above the bubble for assistant messages */}
        {!isUser && hasReasoningParts && combinedReasoning && (
          <div className="mb-2">
            <ReasoningDisplay
              content={combinedReasoning}
              startTime={startTime}
              endTime={endTime}
              expanded={streaming}
              className="shadow-sm"
            />
          </div>
        )}

        {/* Tool parts - displayed above the bubble for assistant messages */}
        {!isUser && hasToolParts && (
          <div className="mb-2 space-y-2">
            {toolParts.map((part) => (
              <ToolCard
                key={part.id}
                part={part}
                compact
                defaultOpen={part.state.status === "error" || streaming}
              />
            ))}
          </div>
        )}

        {!isUser && !streaming && unfinishedTodos.length > 0 && (
          <div className="mb-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-200">
            <div className="mb-1 font-medium">未完成事项</div>
            <ul className="space-y-1">
              {unfinishedTodos.slice(0, 3).map((todo, index) => (
                <li key={`${todo.status}-${todo.content}-${index}`}>
                  {todo.status === "in_progress" && todo.activeForm
                    ? todo.activeForm
                    : todo.content}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Text content bubble */}
        <div
          className={cn(
            "text-sm px-4 py-3 transition-all duration-200",
            isUser
              ? "user-bubble text-white rounded-[18px] rounded-tr-[6px] whitespace-pre-wrap"
              : "assistant-bubble text-foreground rounded-[18px] rounded-tl-[6px]"
          )}
        >
          {isUser ? textContent : (
            <Suspense fallback={<div className="text-muted-foreground">Loading content...</div>}>
              <MessageRendererErrorBoundary>
                <MessageRenderer content={textContent} />
              </MessageRendererErrorBoundary>
            </Suspense>
          )}
        </div>

        {/* Action bar */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-all duration-200 translate-y-0.5 group-hover:translate-y-0">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-muted-foreground/60 hover:text-foreground px-2 py-1 rounded-lg hover:bg-white/5 transition-all"
              aria-label={t("chat.copy")}
              title={t("chat.copy")}
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? t("chat.copied") : t("chat.copy")}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
