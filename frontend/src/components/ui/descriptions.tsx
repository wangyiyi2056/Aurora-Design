import * as React from "react"
import { cn } from "@/lib/utils"

interface DescriptionsProps extends React.HTMLAttributes<HTMLDivElement> {
  column?: number
  bordered?: boolean
  size?: "default" | "small"
}

interface DescriptionItemProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
}

function Descriptions({ className, column = 1, bordered, size, ...props }: DescriptionsProps) {
  return (
    <div
      className={cn(
        "grid gap-2",
        column === 1 && "grid-cols-1",
        column === 2 && "grid-cols-2",
        bordered && "border border-border rounded-md",
        className
      )}
      {...props}
    />
  )
}

function DescriptionItem({ className, label, children, ...props }: DescriptionItemProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1 p-2",
        className
      )}
      {...props}
    >
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  )
}

export { Descriptions, DescriptionItem }