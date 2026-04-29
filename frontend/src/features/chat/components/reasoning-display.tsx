import { useState, useMemo } from "react"
import { Brain, ChevronDown, ChevronRight, Lightbulb, Zap, Eye, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

// === ReAct Section Types ===

export interface ReActSection {
  type: "thought" | "action" | "action_input" | "observation" | "error" | "text"
  content: string
  actionName?: string
}

// === Props ===

interface ReasoningDisplayProps {
  content: string
  expanded?: boolean
  startTime?: number
  endTime?: number
  className?: string
}

// === ReAct Parser ===

export function parseReActContent(content: string): ReActSection[] {
  if (!content || typeof content !== "string") return []

  const sections: ReActSection[] = []
  const normalizedContent = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n")

  const sectionPatterns = [
    { type: "thought" as const, pattern: /(?:^|\n)(?:Thought|思考|💭)\s*[:：]\s*/gi },
    { type: "action" as const, pattern: /(?:^|\n)(?:Action|动作|⚡)\s*[:：]\s*/gi },
    {
      type: "action_input" as const,
      pattern: /(?:^|\n)(?:Action Input|Action_Input|ActionInput|动作输入|输入)\s*[:：]\s*/gi,
    },
    { type: "observation" as const, pattern: /(?:^|\n)(?:Observation|观察|观察结果|👁)\s*[:：]\s*/gi },
  ]

  const matches: { type: ReActSection["type"]; index: number; length: number }[] = []

  for (const { type, pattern } of sectionPatterns) {
    let match
    const regex = new RegExp(pattern.source, pattern.flags)
    while ((match = regex.exec(normalizedContent)) !== null) {
      matches.push({
        type,
        index: match.index,
        length: match[0].length,
      })
    }
  }

  matches.sort((a, b) => a.index - b.index)

  // No matches - return as text or error
  if (matches.length === 0) {
    const errorPatterns = [/error/i, /failed/i, /exception/i, /traceback/i]
    const isError = errorPatterns.some(p => p.test(normalizedContent))
    return [{ type: isError ? "error" : "text", content: normalizedContent.trim() }]
  }

  // Leading text before first match
  if (matches[0].index > 0) {
    const leadingText = normalizedContent.substring(0, matches[0].index).trim()
    if (leadingText) {
      sections.push({ type: "text", content: leadingText })
    }
  }

  // Process each match
  for (let i = 0; i < matches.length; i++) {
    const current = matches[i]
    const next = matches[i + 1]

    const startIndex = current.index + current.length
    const endIndex = next ? next.index : normalizedContent.length

    let sectionContent = normalizedContent.substring(startIndex, endIndex).trim()

    // Extract action name for action sections
    let actionName: string | undefined
    if (current.type === "action") {
      const pipeIndex = sectionContent.indexOf("|")
      if (pipeIndex > 0) {
        actionName = sectionContent.substring(0, pipeIndex).trim()
        sectionContent = sectionContent.substring(pipeIndex + 1).trim()
      } else {
        const firstLineEnd = sectionContent.indexOf("\n")
        if (firstLineEnd > 0) {
          actionName = sectionContent.substring(0, firstLineEnd).trim()
          sectionContent = sectionContent.substring(firstLineEnd + 1).trim()
        } else {
          actionName = sectionContent
          sectionContent = ""
        }
      }
    }

    if (sectionContent || actionName) {
      sections.push({
        type: current.type,
        content: sectionContent,
        actionName,
      })
    }
  }

  return sections
}

// === Section Styling ===

function getSectionIcon(type: ReActSection["type"]) {
  switch (type) {
    case "thought":
      return <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
    case "action":
      return <Zap className="h-3.5 w-3.5 text-blue-500" />
    case "action_input":
      return <Zap className="h-3.5 w-3.5 text-slate-400" />
    case "observation":
      return <Eye className="h-3.5 w-3.5 text-emerald-500" />
    case "error":
      return <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
    default:
      return null
  }
}

function getSectionTitle(type: ReActSection["type"], actionName?: string): string {
  switch (type) {
    case "thought":
      return "Thought"
    case "action":
      return actionName ? `Action: ${actionName}` : "Action"
    case "action_input":
      return "Action Input"
    case "observation":
      return "Observation"
    case "error":
      return "Error"
    default:
      return ""
  }
}

function getSectionStyles(type: ReActSection["type"]) {
  switch (type) {
    case "thought":
      return {
        container: "bg-amber-50/50 dark:bg-amber-900/10 border-l-2 border-amber-400/60 dark:border-amber-500/40",
        header: "text-amber-700 dark:text-amber-400",
        content: "text-amber-900 dark:text-amber-200",
      }
    case "action":
      return {
        container: "bg-blue-50/50 dark:bg-blue-900/10 border-l-2 border-blue-400/60 dark:border-blue-500/40",
        header: "text-blue-700 dark:text-blue-400",
        content: "text-blue-900 dark:text-blue-200",
      }
    case "action_input":
      return {
        container: "bg-slate-50/50 dark:bg-slate-800/30 border-l-2 border-slate-300 dark:border-slate-600",
        header: "text-slate-600 dark:text-slate-400",
        content: "text-slate-800 dark:text-slate-200",
      }
    case "observation":
      return {
        container: "bg-emerald-50/50 dark:bg-emerald-900/10 border-l-2 border-emerald-400/60 dark:border-emerald-500/40",
        header: "text-emerald-700 dark:text-emerald-400",
        content: "text-emerald-900 dark:text-emerald-200",
      }
    case "error":
      return {
        container: "bg-red-50/50 dark:bg-red-900/10 border-l-2 border-red-400/60 dark:border-red-500/40",
        header: "text-red-700 dark:text-red-400",
        content: "text-red-800 dark:text-red-300",
      }
    default:
      return {
        container: "bg-gray-50/50 dark:bg-gray-800/30 border-l-2 border-gray-300 dark:border-gray-600",
        header: "text-gray-600 dark:text-gray-400",
        content: "text-gray-800 dark:text-gray-200",
      }
  }
}

// === Duration Helper ===

function formatDuration(startTime?: number, endTime?: number): string {
  if (!startTime) return ""
  const end = endTime || Date.now()
  const duration = Math.round((end - startTime) / 1000)
  if (duration < 60) return `${duration}s`
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60
  return `${minutes}m ${seconds}s`
}

// === JSON Highlighting ===

function isJsonContent(content: string): boolean {
  const trimmed = content.trim()
  return (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
}

function highlightJson(jsonString: string): React.ReactNode {
  const lines = jsonString.split("\n")

  return (
    <div className="font-mono text-xs leading-relaxed overflow-x-auto">
      {lines.map((line, lineIndex) => {
        const tokens: React.ReactNode[] = []
        let remaining = line
        let keyIndex = 0

        const addToken = (text: string, className: string) => {
          if (text) {
            tokens.push(
              <span key={`${lineIndex}-${keyIndex++}`} className={className}>
                {text}
              </span>
            )
          }
        }

        // Preserve indentation
        const indentMatch = remaining.match(/^(\s*)/)
        if (indentMatch && indentMatch[1]) {
          addToken(indentMatch[1], "")
          remaining = remaining.substring(indentMatch[1].length)
        }

        while (remaining.length > 0) {
          // JSON key
          const keyMatch = remaining.match(/^"([^"\\]|\\.)*"\s*:/)
          if (keyMatch) {
            const colonIndex = keyMatch[0].lastIndexOf(":")
            const keyPart = keyMatch[0].substring(0, colonIndex)
            addToken(keyPart, "text-purple-600 dark:text-purple-400")
            addToken(":", "text-gray-500 dark:text-gray-400")
            remaining = remaining.substring(keyMatch[0].length)
            continue
          }

          // String value
          const stringMatch = remaining.match(/^"([^"\\]|\\.)*"/)
          if (stringMatch) {
            addToken(stringMatch[0], "text-green-600 dark:text-green-400")
            remaining = remaining.substring(stringMatch[0].length)
            continue
          }

          // Number
          const numberMatch = remaining.match(/^-?\d+\.?\d*([eE][+-]?\d+)?/)
          if (numberMatch) {
            addToken(numberMatch[0], "text-blue-600 dark:text-blue-400")
            remaining = remaining.substring(numberMatch[0].length)
            continue
          }

          // Boolean/null
          const boolNullMatch = remaining.match(/^(true|false|null)/)
          if (boolNullMatch) {
            addToken(boolNullMatch[0], "text-orange-600 dark:text-orange-400")
            remaining = remaining.substring(boolNullMatch[0].length)
            continue
          }

          // Brackets
          const bracketMatch = remaining.match(/^[{}\[\]]/)
          if (bracketMatch) {
            addToken(bracketMatch[0], "text-gray-700 dark:text-gray-300 font-semibold")
            remaining = remaining.substring(1)
            continue
          }

          // Punctuation
          const punctMatch = remaining.match(/^[,:\s]+/)
          if (punctMatch) {
            addToken(punctMatch[0], "text-gray-500 dark:text-gray-400")
            remaining = remaining.substring(punctMatch[0].length)
            continue
          }

          // Fallback
          addToken(remaining[0], "text-gray-700 dark:text-gray-300")
          remaining = remaining.substring(1)
        }

        return (
          <div key={lineIndex} className="min-h-[1.25em]">
            {tokens.length > 0 ? tokens : " "}
          </div>
        )
      })}
    </div>
  )
}

// === Sub-Components ===

interface ReActSectionDisplayProps {
  section: ReActSection
  compact?: boolean
}

function ReActSectionDisplay({ section, compact = false }: ReActSectionDisplayProps) {
  const styles = getSectionStyles(section.type)
  const title = getSectionTitle(section.type, section.actionName)
  const icon = getSectionIcon(section.type)

  const isCode = section.type === "action_input" && isJsonContent(section.content)

  // For thought sections, just render content directly
  if (section.type === "thought") {
    return (
      <div className="text-sm text-amber-900 dark:text-amber-200 leading-relaxed whitespace-pre-wrap">
        {section.content.trim()}
      </div>
    )
  }

  // For plain text, render without decoration
  if (section.type === "text") {
    return (
      <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
        {section.content.trim()}
      </div>
    )
  }

  return (
    <div className={cn("rounded-md overflow-hidden transition-all", styles.container, compact ? "p-2" : "p-3")}>
      <div className="flex items-center gap-2 mb-2">
        <div className={cn("flex items-center gap-1.5 font-semibold text-xs uppercase tracking-wide", styles.header)}>
          {icon}
          <span>{title}</span>
        </div>
      </div>

      {section.content && (
        <div className={cn("rounded-md", isCode ? "bg-white/50 dark:bg-black/20 p-2 overflow-x-auto" : "")}>
          {isCode ? (
            highlightJson(section.content)
          ) : (
            <div className={cn("leading-relaxed whitespace-pre-wrap", styles.content, compact ? "text-xs" : "text-sm")}>
              {section.content.trim()}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// === Main Component ===

export function ReasoningDisplay({
  content,
  expanded = false,
  startTime,
  endTime,
  className,
}: ReasoningDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(expanded)

  const sections = useMemo(() => parseReActContent(content), [content])
  const duration = useMemo(() => formatDuration(startTime, endTime), [startTime, endTime])

  // If no content, render nothing
  if (!content || sections.length === 0) {
    return null
  }

  // Check if this is purely thought content (no ReAct structure)
  const hasReActStructure = sections.some(s => s.type !== "text" && s.type !== "thought")

  return (
    <div
      className={cn(
        "rounded-xl overflow-hidden",
        "bg-gradient-to-r from-amber-50/10 to-orange-50/10 dark:from-amber-900/5 dark:to-orange-900/5",
        "border border-amber-500/20 dark:border-amber-500/10",
        className
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "w-full flex items-center justify-between gap-2 px-3 py-2",
          "text-amber-100/80 dark:text-amber-400/80",
          "hover:bg-amber-50/20 dark:hover:bg-amber-900/10",
          "transition-colors duration-150"
        )}
        aria-expanded={isExpanded}
        aria-label="Toggle reasoning display"
      >
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-amber-500" />
          <span className="text-xs font-semibold tracking-wide uppercase">
            Thinking
          </span>
          {duration && (
            <span className="text-xs text-amber-500/60 dark:text-amber-400/60">
              {duration}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-amber-500/60" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-amber-500/60" />
          )}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 space-y-2">
          {hasReActStructure ? (
            sections.map((section, index) => (
              <ReActSectionDisplay
                key={`${section.type}-${index}`}
                section={section}
                compact
              />
            ))
          ) : (
            <div className="text-sm text-amber-900 dark:text-amber-200 leading-relaxed whitespace-pre-wrap">
              {content.trim()}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ReasoningDisplay