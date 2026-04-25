import { PackageOpen } from "lucide-react"
import { cn } from "@/lib/utils"

interface EmptyProps {
  description?: React.ReactNode
  className?: string
}

export function Empty({ description = "暂无数据", className }: EmptyProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-8 text-muted-foreground", className)}>
      <PackageOpen className="h-12 w-12 mb-3 opacity-50" />
      <p className="text-sm">{description}</p>
    </div>
  )
}
