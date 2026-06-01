import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { DocStatus } from "@/services/knowledge-v2"

interface StatusBadgeProps {
  status: DocStatus
  className?: string
  onClick?: () => void
}

const statusConfig: Record<
  DocStatus,
  { label: string; className: string }
> = {
  PROCESSED: {
    label: "Processed",
    className: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800",
  },
  PROCESSING: {
    label: "Processing",
    className: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  },
  PARSING: {
    label: "Parsing",
    className: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  },
  ANALYZING: {
    label: "Analyzing",
    className: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  },
  PREPROCESSED: {
    label: "Preprocessed",
    className: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  },
  FAILED: {
    label: "Failed",
    className: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800",
  },
  PENDING: {
    label: "Pending",
    className: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/50 dark:text-slate-400 dark:border-slate-700",
  },
}

export function StatusBadge({ status, className, onClick }: StatusBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.PENDING
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs font-medium px-2 py-0.5 rounded-full",
        config.className,
        onClick && "cursor-pointer hover:opacity-80 hover:ring-2 hover:ring-primary/30 transition-all",
        className,
      )}
      onClick={onClick}
    >
      {config.label}
    </Badge>
  )
}
