import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * StreamingIndicator - Real-time execution status indicator.
 * Displays current status with animated pulse and elapsed time.
 */

/**
 * Format duration in milliseconds to readable string.
 * Copied from tool-card.tsx for consistency.
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
 * StreamingIndicator props.
 */
export interface StreamingIndicatorProps {
  /** Current status text (e.g., "Executing...", "Thinking...", "Completed") */
  status: string | null
  /** Start time in milliseconds (used for calculating elapsed time) */
  startTime?: number
  /** Current running tool name */
  toolName?: string
  /** Additional className */
  className?: string
}

/**
 * StreamingIndicator - Shows real-time execution status with animated pulse.
 */
export function StreamingIndicator({
  status,
  startTime,
  toolName,
  className,
}: StreamingIndicatorProps) {
  // Store startTime in ref to prevent reset on re-render (e.g., language switch)
  const startTimeRef = React.useRef<number | undefined>(startTime)

  // Only update ref if startTime actually changes to a new value
  if (startTime !== undefined && startTime !== startTimeRef.current) {
    startTimeRef.current = startTime
  }

  // Calculate elapsed time
  const [elapsed, setElapsed] = React.useState<number>(0)

  // Update elapsed time every second when streaming
  React.useEffect(() => {
    const currentStartTime = startTimeRef.current
    if (!currentStartTime || !status) {
      setElapsed(0)
      return
    }

    // Initial calculation
    setElapsed(Date.now() - currentStartTime)

    // Update every second
    const interval = setInterval(() => {
      setElapsed(Date.now() - currentStartTime)
    }, 1000)

    return () => clearInterval(interval)
  }, [status]) // Only depend on status, startTime is tracked via ref

  // Don't render if no status
  if (!status) return null

  // Determine if actively streaming (status contains "..." or active keywords)
  const isStreaming = status.includes("...") ||
    status.toLowerCase().includes("executing") ||
    status.toLowerCase().includes("thinking") ||
    status.toLowerCase().includes("running")

  return (
    <div
      className={cn(
        "flex items-center gap-2",
        "px-3 py-1.5 rounded-full",
        "bg-blue-500/10",
        "border border-blue-500/20",
        "backdrop-blur-sm",
        "transition-all duration-200",
        isStreaming && "animate-pulse-subtle",
        className
      )}
      role="status"
      aria-live="polite"
    >
      {/* Animated pulse dot */}
      {isStreaming && (
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          {/* Ping animation - outer ring */}
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full",
              "bg-blue-400 opacity-75",
              "animate-ping"
            )}
          />
          {/* Pulse animation - solid center */}
          <span
            className={cn(
              "relative inline-flex rounded-full h-2.5 w-2.5",
              "bg-blue-500"
            )}
          />
        </span>
      )}

      {/* Status text */}
      <span
        className={cn(
          "text-sm font-medium",
          "text-blue-600 dark:text-blue-400",
          "truncate"
        )}
      >
        {status}
      </span>

      {/* Tool name */}
      {toolName && (
        <span
          className={cn(
            "text-xs",
            "text-blue-500/70 dark:text-blue-400/70",
            "truncate max-w-[120px]"
          )}
        >
          {toolName}
        </span>
      )}

      {/* Elapsed time */}
      {startTime && elapsed > 0 && (
        <span
          className={cn(
            "text-xs tabular-nums",
            "text-blue-500/60 dark:text-blue-400/60",
            "shrink-0"
          )}
        >
          {formatDuration(elapsed)}
        </span>
      )}
    </div>
  )
}

/**
 * Compact inline streaming indicator for tighter spaces.
 */
export function StreamingIndicatorCompact({
  status,
  startTime,
  className,
}: StreamingIndicatorProps) {
  // Store startTime in ref to prevent reset on re-render
  const startTimeRef = React.useRef<number | undefined>(startTime)

  if (startTime !== undefined && startTime !== startTimeRef.current) {
    startTimeRef.current = startTime
  }

  const [elapsed, setElapsed] = React.useState<number>(0)

  React.useEffect(() => {
    const currentStartTime = startTimeRef.current
    if (!currentStartTime || !status) {
      setElapsed(0)
      return
    }

    setElapsed(Date.now() - currentStartTime)
    const interval = setInterval(() => {
      setElapsed(Date.now() - currentStartTime)
    }, 1000)

    return () => clearInterval(interval)
  }, [status])

  if (!status) return null

  const isStreaming = status.includes("...")

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5",
        "px-2 py-0.5 rounded-md",
        "bg-blue-500/10",
        "border border-blue-500/20",
        "text-xs",
        isStreaming && "animate-pulse-subtle",
        className
      )}
      role="status"
      aria-live="polite"
    >
      {isStreaming && (
        <span className="relative flex h-1.5 w-1.5 shrink-0">
          <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 animate-ping" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
        </span>
      )}
      <span className="text-blue-600 dark:text-blue-400 truncate">
        {status}
      </span>
      {startTime && elapsed > 0 && (
        <span className="text-blue-500/60 dark:text-blue-400/60 tabular-nums shrink-0">
          {formatDuration(elapsed)}
        </span>
      )}
    </span>
  )
}

export default StreamingIndicator