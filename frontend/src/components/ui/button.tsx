import { forwardRef } from "react"
import { Button as AntButton } from "antd"
import type { ButtonProps as AntButtonProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface ButtonProps extends AntButtonProps {
  className?: string
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <AntButton
        ref={ref}
        className={cn(
          "shadow-sm transition-colors duration-fast",
          className
        )}
        {...props}
      >
        {children}
      </AntButton>
    )
  }
)

Button.displayName = "Button"
