import { useEffect, useRef, useState, useCallback } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { Bot, ArrowDown } from "lucide-react"
import type { ChatMessage, ToolPart } from "@/stores/chat-store"
import { useChatStore } from "@/stores/chat-store"
import { ChatMessageItem } from "./chat-message-item"
import { StreamingIndicator } from "./streaming-indicator"
import { ToolCard } from "./tool-card"

export function ChatMessageList({ messages, loading }: ChatMessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)
  const [showScrollButton, setShowScrollButton] = useState(false)

  // Get streaming state from store
  const { streamingParts, streamingStatus } = useChatStore()

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
  }, [messages, loading, streamingParts, streamingStatus, scrollToBottom])

  useEffect(() => {
    const el = parentRef.current
    if (!el) return
    el.addEventListener("scroll", checkNearBottom, { passive: true })
    return () => el.removeEventListener("scroll", checkNearBottom)
  }, [checkNearBottom])

  const virtualItems = virtualizer.getVirtualItems()

  // Get running tool from streaming parts
  const runningTool = streamingParts.find(p => p.type === "tool" && p.state.status === "running") as ToolPart | undefined
  const toolName = runningTool?.tool

  return (
    <div className="relative flex-1">
      <div
        ref={parentRef}
        className="absolute inset-0 overflow-y-auto flex flex-col gap-5 pb-[180px] px-2"
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
            const isLastMessage = virtualItem.index === messages.length - 1
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
                <ChatMessageItem
                  role={msg.role}
                  content={msg.content}
                  startTime={msg.startTime}
                  endTime={msg.endTime}
                  streaming={loading && isLastMessage && msg.role === "assistant"}
                />
              </div>
            )
          })}
        </div>

        {/* Streaming indicator with real-time status */}
        {loading && (
          <div className="flex flex-col gap-3 animate-message-fade-in px-2">
            {/* Avatar */}
            <div className="flex gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] bg-muted/50 text-muted-foreground text-sm border border-border/40 ring-1 ring-white/[0.03]">
                <Bot className="h-4 w-4" />
              </div>

              <div className="flex flex-col gap-2">
                {/* Streaming status indicator */}
                <StreamingIndicator
                  status={streamingStatus || "Thinking..."}
                  startTime={Date.now()}
                  toolName={toolName}
                />

                {/* Show running tool cards during streaming */}
                {streamingParts.filter(p => p.type === "tool" && p.state.status === "running").map((part) => (
                  <ToolCard
                    key={part.id}
                    part={part as ToolPart}
                    compact
                    defaultOpen
                  />
                ))}
              </div>
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
          <ArrowDown className="h-4 w-4 text-foreground/60" />
        </button>
      )}
    </div>
  )
}

interface ChatMessageListProps {
  messages: ChatMessage[]
  loading: boolean
}
