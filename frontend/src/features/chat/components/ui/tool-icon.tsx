import {
  Eye,
  Terminal,
  Code2,
  FileEdit,
  FilePlus,
  Search,
  FileSearch,
  Brain,
  ListTodo,
  LayoutList,
  Globe,
  MessageCircleQuestion,
  HelpCircle,
  Settings,
  CheckCircle2,
  Loader2,
  Copy,
  FolderOpen,
  Layers,
  Zap,
  LucideIcon
} from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Tool icon mapping for ChatBI.
 * Maps tool names to appropriate Lucide icons with consistent styling.
 */

// Icon name to Lucide icon mapping
const TOOL_ICON_MAP: Record<string, LucideIcon> = {
  // Reading/viewing files
  read: Eye,

  // Console/bash commands
  bash: Terminal,
  shell: Terminal,
  command: Terminal,

  // Code editing
  edit: Code2,
  write: FilePlus,
  apply_patch: FileEdit,

  // Search operations
  list: LayoutList,
  glob: FileSearch,
  grep: Search,

  // Web operations
  webfetch: Globe,
  web: Globe,

  // Task management
  task: Layers,
  delegate: Layers,

  // Planning/todo
  todowrite: ListTodo,
  todoread: ListTodo,

  // Skills
  skill: Zap,

  // Questions/interactive
  question: MessageCircleQuestion,

  // Thinking/reasoning
  reasoning: Brain,
  think: Brain,

  // File operations
  folder: FolderOpen,

  // Settings
  settings: Settings,

  // Help
  help: HelpCircle,

  // Status indicators
  success: CheckCircle2,
  loading: Loader2,
  copying: Copy,
}

// Tool type definition
export type ToolName = keyof typeof TOOL_ICON_MAP | string

// Status text mapping for tool operations
export const TOOL_STATUS_TEXT: Record<string, string> = {
  task: "Delegating...",
  delegate: "Delegating...",
  todowrite: "Planning...",
  todoread: "Reading plan...",
  read: "Reading...",
  list: "Searching codebase...",
  grep: "Searching...",
  glob: "Finding files...",
  webfetch: "Fetching...",
  web: "Fetching...",
  edit: "Editing...",
  write: "Writing...",
  apply_patch: "Applying changes...",
  bash: "Running command...",
  shell: "Running command...",
  command: "Running command...",
  reasoning: "Thinking...",
  think: "Thinking...",
  skill: "Loading skill...",
  question: "Waiting for input...",
  success: "Completed",
  loading: "Processing...",
}

/**
 * Get the Lucide icon component for a tool name.
 */
export function getToolIcon(tool: ToolName): LucideIcon {
  return TOOL_ICON_MAP[tool.toLowerCase()] || Settings
}

/**
 * Get the status text for a tool operation.
 */
export function getToolStatusText(tool: string): string {
  return TOOL_STATUS_TEXT[tool.toLowerCase()] || "Processing..."
}

/**
 * Props for the ToolIcon component.
 */
interface ToolIconProps {
  /** Tool name to display icon for */
  tool: ToolName
  /** Icon size variant */
  size?: "xs" | "sm" | "md" | "lg"
  /** Additional className */
  className?: string
  /** Icon color variant */
  variant?: "default" | "muted" | "accent" | "success" | "error"
}

// Size mapping
const SIZE_MAP: Record<string, { icon: string; wrapper: string }> = {
  xs: { icon: "h-3 w-3", wrapper: "h-4 w-4" },
  sm: { icon: "h-3.5 w-3.5", wrapper: "h-5 w-5" },
  md: { icon: "h-4 w-4", wrapper: "h-6 w-6" },
  lg: { icon: "h-5 w-5", wrapper: "h-8 w-8" },
}

// Color variant mapping
const VARIANT_MAP: Record<string, string> = {
  default: "text-foreground",
  muted: "text-muted-foreground",
  accent: "text-accent-foreground",
  success: "text-emerald-500",
  error: "text-destructive",
}

/**
 * ToolIcon component - displays the appropriate icon for a tool.
 */
export function ToolIcon({
  tool,
  size = "sm",
  className,
  variant = "muted"
}: ToolIconProps) {
  const Icon = getToolIcon(tool)
  const sizeConfig = SIZE_MAP[size]

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center shrink-0",
        sizeConfig.wrapper,
        "rounded-md",
        "bg-surface/40 backdrop-blur-sm",
        "border border-border/30",
        className
      )}
      aria-hidden="true"
      data-tool={tool}
    >
      <Icon
        className={cn(
          sizeConfig.icon,
          VARIANT_MAP[variant]
        )}
      />
    </span>
  )
}

/**
 * Inline tool icon without wrapper - for compact display.
 */
export function ToolIconInline({
  tool,
  size = "sm",
  className,
  variant = "muted"
}: ToolIconProps) {
  const Icon = getToolIcon(tool)
  const sizeConfig = SIZE_MAP[size]

  return (
    <Icon
      className={cn(
        sizeConfig.icon,
        VARIANT_MAP[variant],
        className
      )}
      aria-hidden="true"
    />
  )
}

/**
 * ToolIcon with status badge - shows tool icon with a status indicator.
 */
interface ToolIconWithStatusProps extends ToolIconProps {
  /** Current status */
  status?: "pending" | "running" | "success" | "error"
  /** Whether to show status text */
  showText?: boolean
}

export function ToolIconWithStatus({
  tool,
  status = "pending",
  showText = false,
  size = "sm",
  className,
  variant = "muted"
}: ToolIconWithStatusProps) {
  const Icon = getToolIcon(tool)
  const sizeConfig = SIZE_MAP[size]
  const statusText = showText ? getToolStatusText(tool) : undefined

  const statusVariant = status === "success" ? "success"
    : status === "error" ? "error"
    : status === "running" ? "accent"
    : variant

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex items-center justify-center shrink-0",
          sizeConfig.wrapper,
          "rounded-md",
          "bg-surface/40 backdrop-blur-sm",
          "border border-border/30",
          status === "running" && "animate-pulse"
        )}
      >
        {status === "running"
          ? <Loader2 className={cn(sizeConfig.icon, "animate-spin text-accent-foreground")} />
          : <Icon className={cn(sizeConfig.icon, VARIANT_MAP[statusVariant])} />
        }
      </span>
      {statusText && (
        <span className="text-xs text-muted-foreground truncate">
          {statusText}
        </span>
      )}
    </span>
  )
}

// Export the icon map for direct access
export { TOOL_ICON_MAP }

// Default export
export default ToolIcon