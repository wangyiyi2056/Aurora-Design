import { Loader2 } from "lucide-react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const spinnerVariants = cva("animate-spin text-muted-foreground", {
  variants: {
    size: {
      default: "h-4 w-4",
      sm: "h-3 w-3",
      lg: "h-6 w-6",
      xl: "h-8 w-8",
    },
  },
  defaultVariants: {
    size: "default",
  },
})

interface SpinnerProps extends VariantProps<typeof spinnerVariants> {
  className?: string
  tip?: string
}

function Spinner({ size, className, tip }: SpinnerProps) {
  return (
    <div className="flex items-center justify-center gap-2">
      <Loader2 className={cn(spinnerVariants({ size }), className)} />
      {tip && <span className="text-sm text-muted-foreground">{tip}</span>}
    </div>
  )
}

export { Spinner, spinnerVariants }