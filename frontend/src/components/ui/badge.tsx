import { forwardRef } from "react"
import { Badge as AntBadge } from "antd"
import type { BadgeProps as AntBadgeProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface BadgeProps extends AntBadgeProps {
  className?: string
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, ...props }, ref) => {
    return (
      <AntBadge
        ref={ref}
        className={cn("", className)}
        {...props}
      />
    )
  }
)

Badge.displayName = "Badge"
