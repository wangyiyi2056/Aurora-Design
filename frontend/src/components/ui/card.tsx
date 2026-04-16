import { forwardRef } from "react"
import { Card as AntCard } from "antd"
import type { CardProps as AntCardProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface CardProps extends AntCardProps {
  className?: string
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <AntCard
        ref={ref}
        className={cn(
          "bg-surface border-border shadow-md rounded-lg",
          className
        )}
        {...props}
      >
        {children}
      </AntCard>
    )
  }
)

Card.displayName = "Card"
