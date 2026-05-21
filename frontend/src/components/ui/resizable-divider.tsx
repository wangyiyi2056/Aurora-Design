import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"

interface ResizableDividerProps {
  /**
   * 左侧面板的初始宽度（像素）
   */
  initialLeftWidth?: number
  /**
   * 左侧面板的最小宽度（像素）
   */
  minLeftWidth?: number
  /**
   * 左侧面板的最大宽度（像素）
   */
  maxLeftWidth?: number
  /**
   * 左侧面板内容
   */
  leftPanel: React.ReactNode
  /**
   * 右侧面板内容
   */
  rightPanel: React.ReactNode
  /**
   * 是否显示右侧面板
   */
  showRightPanel?: boolean
  /**
   * 容器类名
   */
  className?: string
}

export function ResizableDivider({
  initialLeftWidth = 500,
  minLeftWidth = 350,
  maxLeftWidth = 750,
  leftPanel,
  rightPanel,
  showRightPanel = true,
  className,
}: ResizableDividerProps) {
  const [leftWidth, setLeftWidth] = useState(initialLeftWidth)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const leftPanelRef = useRef<HTMLDivElement>(null)
  const pointerFrameRef = useRef<number | null>(null)
  const pendingClientXRef = useRef<number | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)
  const currentWidthRef = useRef(initialLeftWidth)
  const startRef = useRef<{ clientX: number; width: number; isRtl: boolean } | null>(null)
  const leftWidthRef = useRef(leftWidth)

  const updateWidth = useCallback((newWidth: number) => {
    const clampedWidth = Math.max(minLeftWidth, Math.min(maxLeftWidth, newWidth))
    currentWidthRef.current = clampedWidth

    if (leftPanelRef.current) {
      leftPanelRef.current.style.width = `${clampedWidth}px`
    }
  }, [minLeftWidth, maxLeftWidth])

  const finishResize = useCallback((commit = true) => {
    cleanupRef.current?.()
    cleanupRef.current = null
    setIsDragging(false)

    if (pointerFrameRef.current !== null) {
      cancelAnimationFrame(pointerFrameRef.current)
      pointerFrameRef.current = null
    }

    pendingClientXRef.current = null
    startRef.current = null
    if (commit) setLeftWidth(currentWidthRef.current)
  }, [])

  const handlePointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    const container = containerRef.current
    if (!container) return

    event.preventDefault()
    event.currentTarget.focus()
    event.currentTarget.setPointerCapture(event.pointerId)
    cleanupRef.current?.()
    setIsDragging(true)

    startRef.current = {
      clientX: event.clientX,
      width: leftWidthRef.current,
      isRtl: window.getComputedStyle(container).direction === "rtl",
    }

    const previousUserSelect = document.body.style.userSelect
    const previousCursor = document.body.style.cursor
    document.body.style.userSelect = "none"
    document.body.style.cursor = "col-resize"

    const updateFromClientX = (clientX: number) => {
      const start = startRef.current
      if (!start) return
      const delta = clientX - start.clientX
      const nextWidth = start.width + (start.isRtl ? -delta : delta)
      updateWidth(nextWidth)
    }

    const flushPendingMove = () => {
      if (pointerFrameRef.current !== null) {
        cancelAnimationFrame(pointerFrameRef.current)
        pointerFrameRef.current = null
      }
      const clientX = pendingClientXRef.current
      pendingClientXRef.current = null
      if (clientX !== null) updateFromClientX(clientX)
    }

    const handlePointerMove = (moveEvent: PointerEvent) => {
      pendingClientXRef.current = moveEvent.clientX
      if (pointerFrameRef.current !== null) return
      pointerFrameRef.current = requestAnimationFrame(() => {
        pointerFrameRef.current = null
        flushPendingMove()
      })
    }

    const handlePointerEnd = () => {
      flushPendingMove()
      finishResize(true)
    }

    const handlePointerCancel = () => {
      flushPendingMove()
      updateWidth(startRef.current?.width ?? leftWidthRef.current)
      finishResize(false)
    }

    const cleanup = () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", handlePointerEnd)
      window.removeEventListener("pointercancel", handlePointerCancel)
      window.removeEventListener("blur", handlePointerCancel)
      document.body.style.userSelect = previousUserSelect
      document.body.style.cursor = previousCursor
    }

    cleanupRef.current = cleanup
    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", handlePointerEnd)
    window.addEventListener("pointercancel", handlePointerCancel)
    window.addEventListener("blur", handlePointerCancel)
  }, [finishResize, updateWidth])

  useEffect(() => () => finishResize(false), [finishResize])

  useEffect(() => {
    if (!showRightPanel) {
      setLeftWidth(initialLeftWidth)
      currentWidthRef.current = initialLeftWidth
      if (leftPanelRef.current) {
        leftPanelRef.current.style.width = "100%"
      }
    }
  }, [showRightPanel, initialLeftWidth])

  useLayoutEffect(() => {
    currentWidthRef.current = leftWidth
    leftWidthRef.current = leftWidth
    if (leftPanelRef.current && showRightPanel) {
      leftPanelRef.current.style.width = `${leftWidth}px`
    }
  }, [leftWidth, showRightPanel])

  return (
    <div
      ref={containerRef}
      className={cn(
        "flex h-full min-w-0 overflow-hidden bg-background",
        isDragging && "[&_iframe]:pointer-events-none",
        !showRightPanel && "justify-center", // 没有右侧面板时居中
        className,
      )}
    >
      {/* 左侧面板 */}
      <div
        ref={leftPanelRef}
        className={cn(
          "min-w-0",
          showRightPanel && "border-r" // 只有显示右侧面板时才显示边框
        )}
        style={{
          width: showRightPanel ? `${leftWidth}px` : "100%",
          maxWidth: showRightPanel ? undefined : `${maxLeftWidth}px`,
          flexShrink: 0,
        }}
      >
        {leftPanel}
      </div>

      {/* 可拖动的分隔线 */}
      {showRightPanel && (
        <div
          className={cn(
            "group relative w-2 flex-shrink-0 cursor-col-resize touch-none bg-border transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            isDragging && "bg-primary/30"
          )}
          role="separator"
          aria-orientation="vertical"
          aria-valuemin={minLeftWidth}
          aria-valuemax={maxLeftWidth}
          aria-valuenow={Math.round(leftWidth)}
          tabIndex={0}
          onPointerDown={handlePointerDown}
        >
          {/* 可视化拖动区域 */}
          <div className="absolute inset-y-0 -left-1 -right-1" />
          
          {/* 拖动指示器 */}
          <div className="absolute left-1/2 top-1/2 h-12 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-muted-foreground/20 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
        </div>
      )}

      {/* 右侧面板 */}
      {showRightPanel && (
        <div className="min-w-0 flex-1 bg-background">
          {rightPanel}
        </div>
      )}
    </div>
  )
}
