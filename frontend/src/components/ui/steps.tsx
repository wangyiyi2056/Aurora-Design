import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

interface Step {
  title: string
  key?: string
}

interface StepsProps {
  steps: Step[]
  current: number
  className?: string
}

export function Steps({ steps, current, className }: StepsProps) {
  return (
    <div className={cn("flex items-center w-full", className)}>
      {steps.map((step, index) => {
        const isCompleted = index < current
        const isActive = index === current
        const isLast = index === steps.length - 1

        return (
          <div key={step.key || index} className={cn("flex items-center", isLast ? "flex-1" : "flex-1")}>
            <div className="flex flex-col items-center flex-1">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium border-2 transition-colors",
                  isCompleted && "bg-primary text-primary-foreground border-primary",
                  isActive && "border-primary text-primary",
                  !isCompleted && !isActive && "border-muted-foreground text-muted-foreground"
                )}
              >
                {isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : (
                  index + 1
                )}
              </div>
              <span
                className={cn(
                  "mt-2 text-sm",
                  isActive ? "text-foreground font-medium" : "text-muted-foreground"
                )}
              >
                {step.title}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "h-0.5 flex-1 mx-2 -mt-5",
                  index < current ? "bg-primary" : "bg-muted"
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
