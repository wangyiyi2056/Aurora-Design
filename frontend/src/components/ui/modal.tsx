import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

interface ModalProps {
  title?: string
  open: boolean
  onCancel?: () => void
  onOk?: () => void
  okText?: string
  cancelText?: string
  children?: React.ReactNode
  className?: string
}

export function Modal({ title, open, onCancel, onOk, okText = "确定", cancelText = "取消", children, className }: ModalProps) {
  return (
    <Dialog open={open} onOpenChange={(open) => !open && onCancel?.()}>
      <DialogContent className={className}>
        {title && (
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
        )}
        {children}
        {(onOk || onCancel) && (
          <DialogFooter>
            {onCancel && (
              <Button variant="outline" onClick={onCancel}>
                {cancelText}
              </Button>
            )}
            {onOk && <Button onClick={onOk}>{okText}</Button>}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
