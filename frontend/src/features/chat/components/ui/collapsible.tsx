import * as React from "react"
import * as CollapsiblePrimitive from "@radix-ui/react-collapsible"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Collapsible component with glass-effect styling and smooth animations.
 * Built on Radix UI Collapsible primitive for accessibility and keyboard support.
 */

interface CollapsibleProps extends React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Root> {
  /** Optional custom trigger styling */
  triggerClassName?: string
  /** Optional custom content styling */
  contentClassName?: string
  /** Whether to show a chevron indicator */
  showChevron?: boolean
  /** Custom trigger element (overrides default trigger) */
  trigger?: React.ReactNode
}

const Collapsible = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Root>,
  CollapsibleProps
>(({
  className,
  triggerClassName,
  contentClassName,
  showChevron = true,
  trigger,
  children,
  open,
  defaultOpen,
  onOpenChange,
  disabled,
  ...props
}, ref) => {
  return (
    <CollapsiblePrimitive.Root
      ref={ref}
      open={open}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
      disabled={disabled}
      className={cn(
        "group/collapsible",
        className
      )}
      {...props}
    >
      {children}
    </CollapsiblePrimitive.Root>
  )
})
Collapsible.displayName = "Collapsible"

/**
 * Default trigger with chevron indicator and glass-effect styling.
 */
const CollapsibleTrigger = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Trigger> & {
    /** Whether to show a chevron indicator */
    showChevron?: boolean
    /** Trigger label/content */
    label?: React.ReactNode
  }
>(({ className, showChevron = true, label, children, ...props }, ref) => {
  // Provide default aria-label when no visible content is provided
  const ariaLabel = !children && !label ? "Toggle collapsible section" : undefined

  return (
    <CollapsiblePrimitive.Trigger
      ref={ref}
      aria-label={ariaLabel}
      className={cn(
        "flex items-center gap-2 w-full",
        "px-3 py-2 rounded-lg",
        "bg-surface/50 backdrop-blur-sm border border-border/40",
        "hover:bg-surface/70 hover:border-border/60",
        "text-sm text-foreground font-medium",
        "transition-all duration-200 ease-out",
        "cursor-pointer select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        "data-[state=open]:bg-surface/70",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      {...props}
    >
      {showChevron && (
        <ChevronRight
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground",
            "transition-transform duration-200 ease-out",
            "group-data-[state=open]/collapsible:rotate-90"
          )}
        />
      )}
      {children || label}
    </CollapsiblePrimitive.Trigger>
  )
})
CollapsibleTrigger.displayName = "CollapsibleTrigger"

/**
 * Collapsible content with smooth animation.
 */
const CollapsibleContent = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Content>
>(({ className, children, ...props }, ref) => {
  return (
    <CollapsiblePrimitive.Content
      ref={ref}
      className={cn(
        "overflow-hidden",
        "data-[state=closed]:animate-collapsible-closed",
        "data-[state=open]:animate-collapsible-open",
        className
      )}
      {...props}
    >
      <div
        className={cn(
          "mt-1 p-3 rounded-lg",
          "bg-surface/30 backdrop-blur-sm border border-border/30",
          "text-sm text-muted-foreground"
        )}
      >
        {children}
      </div>
    </CollapsiblePrimitive.Content>
  )
})
CollapsibleContent.displayName = "CollapsibleContent"

/**
 * Simple collapsible wrapper for tool/reasoning display.
 * Pre-styled with glass-effect and inline trigger.
 */
interface CollapsibleBoxProps {
  /** Header/trigger content */
  header: React.ReactNode
  /** Expandable content */
  content: React.ReactNode
  /** Initial open state */
  defaultOpen?: boolean
  /** Controlled open state */
  open?: boolean
  /** Open change callback */
  onOpenChange?: (open: boolean) => void
  /** Additional styling */
  className?: string
  /** Header styling variant */
  variant?: "default" | "compact" | "tool"
}

function CollapsibleBox({
  header,
  content,
  defaultOpen = false,
  open,
  onOpenChange,
  className,
  variant = "default"
}: CollapsibleBoxProps) {
  const variantStyles = {
    default: "px-3 py-2 rounded-lg bg-surface/50 backdrop-blur-sm border border-border/40",
    compact: "px-2 py-1.5 rounded-md bg-muted/30 border border-border/30",
    tool: "px-2 py-1 rounded-md bg-surface/40 backdrop-blur-sm border border-border/40 text-xs"
  }

  return (
    <CollapsiblePrimitive.Root
      open={open}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
      className={cn("group/collapsible", className)}
    >
      <CollapsiblePrimitive.Trigger
        className={cn(
          "flex items-center gap-2 w-full",
          variantStyles[variant],
          "hover:bg-surface/70 hover:border-border/60",
          "transition-all duration-150 ease-out",
          "cursor-pointer select-none",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/30"
        )}
      >
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            "text-muted-foreground/70",
            "transition-transform duration-150",
            "group-data-[state=open]/collapsible:rotate-90"
          )}
        />
        <span className="flex-1 truncate">{header}</span>
      </CollapsiblePrimitive.Trigger>
      <CollapsiblePrimitive.Content
        className={cn(
          "overflow-hidden",
          "data-[state=closed]:animate-collapsible-closed",
          "data-[state=open]:animate-collapsible-open"
        )}
      >
        <div className={cn(
          variant === "tool" ? "mt-1 p-2 rounded-md text-xs" : "mt-2 p-3 rounded-lg text-sm",
          "bg-surface/20 border border-border/20",
          "text-muted-foreground"
        )}>
          {content}
        </div>
      </CollapsiblePrimitive.Content>
    </CollapsiblePrimitive.Root>
  )
}

// Export primitives for custom composition
export {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
  CollapsibleBox,
  CollapsiblePrimitive
}

// Default export for convenience
export default Collapsible
