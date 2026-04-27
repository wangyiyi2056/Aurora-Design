import { useEffect, useRef, useState, useCallback } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { Bot } from "lucide-react"
import { ChatMessageItem } from "./chat-message-item"
import type { ChatMessage } from "@/stores/chat-store"

function ThinkingDots() {
  return (
    <div className="flex items-center gap-2 h-5">
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "0ms" }} />
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "150ms" }} />
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "300ms" }} />
      <span className="text-xs text-muted-foreground/50 ml-1">AI thinking...</span>
    </div>
  )
}

export function ChatMessageList({ messages, loading }: ChatMessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)
  const [showScrollButton, setShowScrollButton] = useState(false)

  const checkNearBottom = useCallback(() => {
    const el = parentRef.current
    if (!el) return
    const threshold = 80
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    isNearBottomRef.current = distance < threshold
    setShowScrollButton(!isNearBottomRef.current)
  }, [])

  const scrollToBottom = useCallback((smooth = true) => {
    bottomRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "instant" })
  }, [])

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    measureElement: (el) => el.getBoundingClientRect().height,
    overscan: 5,
  })

  useEffect(() => {
    if (isNearBottomRef.current) {
      scrollToBottom()
    }
  }, [messages, loading, scrollToBottom])

  useEffect(() => {
    const el = parentRef.current
    if (!el) return
    el.addEventListener("scroll", checkNearBottom, { passive: true })
    return () => el.removeEventListener("scroll", checkNearBottom)
  }, [checkNearBottom])

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div className="relative flex-1">
      <div
        ref={parentRef}
        className="absolute inset-0 overflow-y-auto flex flex-col gap-5 pb-4 px-2"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualItems.map((virtualItem) => {
            const msg = messages[virtualItem.index]
            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualItem.start}px)`,
                  paddingBottom: "20px",
                }}
              >
                <ChatMessageItem role={msg.role} content={msg.content} />
              </div>
            )
          })}
        </div>
        {loading && (
          <div className="flex gap-3 animate-message-fade-in px-2">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] bg-muted/50 text-muted-foreground text-sm border border-border/40 ring-1 ring-white/[0.03]">
              <Bot className="h-4 w-4" />
            </div>
            <div className="assistant-bubble text-foreground text-sm px-4 py-3 rounded-[18px] rounded-tl-[6px] min-w-[80px]">
              <ThinkingDots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {showScrollButton && (
        <button
          type="button"
          onClick={() => {
            scrollToBottom()
            isNearBottomRef.current = true
            setShowScrollButton(false)
          }}
          className="absolute bottom-4 right-4 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-background/80 backdrop-blur border border-border/40 shadow-lg hover:bg-background transition-colors"
          aria-label="Scroll to bottom"
        >
          <svg
            className="h-4 w-4 text-foreground/60"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}
    </div>
  )
}

interface ChatMessageListProps {
  messages: ChatMessage[]
  loading: boolean
}
