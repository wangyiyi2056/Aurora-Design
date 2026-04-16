import { Modal as AntModal } from "antd"
import type { ModalProps as AntModalProps } from "antd"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface ModalProps extends AntModalProps {
  className?: string
}

export function Modal({ className, wrapClassName, children, ...props }: ModalProps) {
  return (
    <AntModal
      className={cn("", className)}
      wrapClassName={cn("ant-modal-root-custom", wrapClassName)}
      {...props}
    >
      {children}
    </AntModal>
  )
}
