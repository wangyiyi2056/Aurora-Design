import { forwardRef } from "react"
import { Input as AntInput } from "antd"
import type { InputProps as AntInputProps, InputRef } from "antd/es/input"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface InputProps extends AntInputProps {
  className?: string
}

export const Input = forwardRef<InputRef, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <AntInput
        ref={ref}
        className={cn(
          "bg-surface-elevated border-border text-text placeholder:text-text-secondary focus:border-primary focus:ring-1 focus:ring-primary",
          className
        )}
        {...props}
      />
    )
  }
)

Input.displayName = "Input"
