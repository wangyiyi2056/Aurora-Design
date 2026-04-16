import { Empty as AntEmpty } from "antd"
import type { EmptyProps as AntEmptyProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface EmptyProps extends AntEmptyProps {
  className?: string
}

export function Empty({ className, ...props }: EmptyProps) {
  return (
    <AntEmpty
      className={cn("text-text-secondary", className)}
      {...props}
    />
  )
}
