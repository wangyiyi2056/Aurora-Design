import { forwardRef } from "react"
import { Select as AntSelect } from "antd"
import type { SelectProps as AntSelectProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface SelectProps<T = unknown> extends AntSelectProps<T> {
  className?: string
}

export const Select = forwardRef<any, SelectProps>(
  ({ className, ...props }, ref) => {
    return (
      <AntSelect
        ref={ref}
        className={cn("min-w-[8rem]", className)}
        popupClassName={cn(
          "bg-surface-elevated border-border",
          props.popupClassName as string | undefined
        )}
        {...props}
      />
    )
  }
)

Select.displayName = "Select"
