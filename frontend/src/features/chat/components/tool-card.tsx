import * as React from "react"
import { CheckCircle2, XCircle, Loader2, Copy, Check, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { getToolStatusText, ToolIcon } from "./ui/tool-icon"
import { CollapsibleBox } from "./ui/collapsible"
import type { ToolPart } from "@/stores/chat-store"

/**
 * ToolCard - Tool execution visualization component.
 * Displays tool name, status, and collapsible input/output content.
 */

// Status color mapping
const STATUS_COLORS = {
  pending: {
    border: "border-border/40",
    bg: "bg-surface/30",
    indicator: "text-muted-foreground",
    badge: "bg-muted/50 text-muted-foreground",
  },
  running: {
    border: "border-blue-500/50",
    bg: "bg-blue-500/5",
    indicator: "text-blue-500",
    badge: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  },
  completed: {
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/5",
    indicator: "text-emerald-500",
    badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  error: {
    border: "border-red-500/50",
    bg: "bg-red-500/5",
    indicator: "text-red-500",
    badge: "bg-red-500/10 text-red-600 dark:text-red-400",
  },
}

// Tool title mapping
const TOOL_TITLE_MAP: Record<string, string> = {
  read: "Read File",
  list: "List Directory",
  glob: "Find Files",
  grep: "Search Content",
  bash: "Run Command",
  shell: "Run Command",
  edit: "Edit File",
  write: "Write File",
  task: "Delegate Task",
  delegate: "Delegate Task",
  todowrite: "Update Todo",
  todoread: "Read Todo",
  webfetch: "Fetch Web",
  web: "Fetch Web",
  question: "Ask Question",
  apply_patch: "Apply Patch",
  skill: "Load Skill",
  reasoning: "Reasoning",
  python: "Execute Python",
  python_execute: "Execute Python",
  data_profile: "Profile Data",
  sql: "Execute Query",
}

/**
 * Get human-readable title for a tool.
 */
function getToolTitle(tool: string): string {
  return TOOL_TITLE_MAP[tool.toLowerCase()] || tool
}

/**
 * Get subtitle/context from tool input.
 */
function getToolSubtitle(tool: string, input?: Record<string, unknown>): string | undefined {
  if (!input) return undefined

  switch (tool.toLowerCase()) {
    case "read":
    case "edit":
    case "write":
      return input.filePath ? getFilename(input.filePath as string) : undefined
    case "glob":
      return input.pattern as string | undefined
    case "grep":
      return input.pattern as string | undefined
    case "bash":
    case "shell":
    case "command":
      return input.description as string | undefined
    case "task":
    case "delegate":
      return input.description as string | undefined
    case "webfetch":
    case "web":
      return input.url as string | undefined
    case "list":
      return input.path ? getFilename(input.path as string) : undefined
    case "python":
    case "python_execute":
      return input.code ? "Python code" : undefined
    case "sql":
      return input.query ? "SQL query" : undefined
    default:
      // Try common input keys
      return (input.value || input.name || input.query || input.argument) as string | undefined
  }
}

/**
 * Extract filename from path.
 */
function getFilename(path: string | undefined): string {
  if (!path) return ""
  const parts = path.split("/")
  return parts[parts.length - 1] || path
}

/**
 * Format duration in milliseconds to readable string.
 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds}s`
}

/**
 * Normalize text content from various formats.
 */
function normalizeText(value: unknown): string {
  if (typeof value === "string") return value
  if (value && typeof value === "object") {
    const todoValue = (value as Record<string, unknown>).TODO
    if (typeof todoValue === "string") return todoValue
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return value == null ? "" : String(value)
}

/**
 * ToolCard props.
 */
export interface ToolCardProps {
  /** Tool part data from chat store */
  part: ToolPart
  /** Initial open state for collapsible */
  defaultOpen?: boolean
  /** Controlled open state */
  open?: boolean
  /** Open change callback */
  onOpenChange?: (open: boolean) => void
  /** Additional className */
  className?: string
  /** Whether to show execution time */
  showTime?: boolean
  /** Compact mode - smaller styling */
  compact?: boolean
}

/**
 * Status indicator component.
 */
function StatusIndicator({ status }: { status: "pending" | "running" | "completed" | "error" }) {
  const colors = STATUS_COLORS[status]

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center shrink-0",
        "h-5 w-5 rounded-full",
        colors.badge,
        "transition-all duration-200"
      )}
      aria-label={status}
    >
      {status === "running" && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status === "completed" && (
        <CheckCircle2 className="h-3 w-3" />
      )}
      {status === "error" && (
        <XCircle className="h-3 w-3" />
      )}
      {status === "pending" && (
        <Clock className="h-3 w-3" />
      )}
    </span>
  )
}

/**
 * Copy button with success state.
 */
function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = React.useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation()
      try {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        // Clipboard access may be blocked; log for debugging
        if (process.env.NODE_ENV === "development") {
          console.debug("[CopyButton] Clipboard write failed:", err)
        }
      }
    },
    [text]
  )

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "flex-shrink-0 p-1.5 rounded-md",
        "text-muted-foreground/60 hover:text-foreground",
        "hover:bg-surface/50",
        "transition-all duration-150",
        copied && "text-emerald-500",
        className
      )}
      aria-label={copied ? "Copied" : "Copy to clipboard"}
    >
      {copied ? (
        <Check className="h-3 w-3" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </button>
  )
}

/**
 * Tool content display - shows input/output with copy functionality.
 */
function ToolContent({
  input,
  output,
  error,
  compact = false,
}: {
  input?: Record<string, unknown>
  output?: string
  error?: string
  compact?: boolean
}) {
  const hasInput = input && Object.keys(input).length > 0
  const hasOutput = !!output
  const hasError = !!error

  if (!hasInput && !hasOutput && !hasError) {
    return null
  }

  return (
    <div className={cn(
      "space-y-2",
      compact && "text-xs"
    )}>
      {/* Error display */}
      {hasError && (
        <div
          className={cn(
            "p-2 rounded-md",
            "bg-red-500/10 border border-red-500/30",
            "text-red-600 dark:text-red-400"
          )}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <XCircle className="h-3.5 w-3.5" />
            <span className="font-medium text-xs">Error</span>
          </div>
          <pre className="text-xs whitespace-pre-wrap break-words overflow-auto max-h-40">
            {error}
          </pre>
        </div>
      )}

      {/* Input display */}
      {hasInput && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground/70 font-medium">Input</span>
          <div className="group relative">
            <pre
              className={cn(
                "p-2 rounded-md",
                "bg-surface/40 border border-border/30",
                "text-muted-foreground",
                "whitespace-pre-wrap break-words overflow-auto",
                compact ? "text-xs max-h-32" : "text-xs max-h-60"
              )}
            >
              {normalizeText(input)}
            </pre>
            <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <CopyButton text={normalizeText(input)} />
            </div>
          </div>
        </div>
      )}

      {/* Output display */}
      {hasOutput && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground/70 font-medium">Output</span>
          <div className="group relative">
            <pre
              className={cn(
                "p-2 rounded-md",
                "bg-surface/40 border border-border/30",
                "text-muted-foreground",
                "whitespace-pre-wrap break-words overflow-auto",
                compact ? "text-xs max-h-32" : "text-xs max-h-60"
              )}
            >
              {normalizeText(output)}
            </pre>
            <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <CopyButton text={normalizeText(output)} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * ToolCard - Main component for displaying tool execution.
 */
export function ToolCard({
  part,
  defaultOpen = false,
  open,
  onOpenChange,
  className,
  showTime = true,
  compact = false,
}: ToolCardProps) {
  const { tool, state } = part
  const { status, input, output, error, metadata } = state

  // Get display values
  const title = getToolTitle(tool)
  const subtitle = getToolSubtitle(tool, input)
  const statusText = getToolStatusText(tool)

  // Calculate duration if metadata has timestamps
  const duration = React.useMemo(() => {
    if (!metadata?.startTime || !metadata?.endTime) return undefined
    return formatDuration((metadata.endTime as number) - (metadata.startTime as number))
  }, [metadata])

  // Status styling
  const statusColors = STATUS_COLORS[status]
  const isRunning = status === "running"
  const hasError = status === "error"
  const isCompleted = status === "completed"

  // Determine if content should be shown
  const hasContent = !!input || !!output || !!error
  const shouldOpenOnError = hasError && defaultOpen === false

  // Header content with status
  const header = (
    <div className="flex items-center gap-2 min-w-0 flex-1">
      {/* Tool icon */}
      <ToolIcon
        tool={tool}
        size={compact ? "xs" : "sm"}
        variant={hasError ? "error" : isCompleted ? "success" : isRunning ? "accent" : "muted"}
        className={cn(
          isRunning && "animate-pulse"
        )}
      />

      {/* Title and subtitle */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "font-medium truncate",
              compact ? "text-xs" : "text-sm",
              statusColors.indicator
            )}
          >
            {title}
          </span>
          {subtitle && (
            <span
              className={cn(
                "truncate text-muted-foreground/70",
                compact ? "text-[10px]" : "text-xs"
              )}
            >
              {subtitle}
            </span>
          )}
        </div>
      </div>

      {/* Status indicator */}
      <div className="flex items-center gap-1.5 shrink-0">
        {isRunning && (
          <span className={cn(
            "text-xs",
            compact && "text-[10px]",
            statusColors.indicator
          )}>
            {statusText}
          </span>
        )}
        <StatusIndicator status={status} />
      </div>

      {/* Duration */}
      {showTime && duration && (
        <span className="text-[10px] text-muted-foreground/50 shrink-0 tabular-nums">
          {duration}
        </span>
      )}
    </div>
  )

  // Content to display
  const content = hasContent ? (
    <ToolContent
      input={input}
      output={output}
      error={error}
      compact={compact}
    />
  ) : null

  // If no content, just show the header
  if (!hasContent) {
    return (
      <div
        className={cn(
          "flex items-center gap-2",
          "px-3 py-2 rounded-lg",
          "bg-surface/40 backdrop-blur-sm",
          "border",
          statusColors.border,
          statusColors.bg,
          "transition-all duration-200",
          className
        )}
        data-tool={tool}
        data-status={status}
      >
        {header}
      </div>
    )
  }

  // With content, use collapsible
  return (
    <div
      className={cn(
        "tool-card",
        className
      )}
      data-tool={tool}
      data-status={status}
    >
      <CollapsibleBox
        header={header}
        content={content}
        defaultOpen={shouldOpenOnError || defaultOpen}
        open={open}
        onOpenChange={onOpenChange}
        variant={compact ? "tool" : "default"}
        className={cn(
          "rounded-lg",
          "border",
          statusColors.border,
          statusColors.bg,
          "transition-all duration-200"
        )}
      />
    </div>
  )
}

/**
 * Compact tool card for inline display in message bubbles.
 */
export function ToolCardCompact(props: ToolCardProps) {
  return <ToolCard {...props} compact />
}

// Default export
export default ToolCard