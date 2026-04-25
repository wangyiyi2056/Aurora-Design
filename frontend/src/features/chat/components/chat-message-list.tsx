import { useEffect, useRef } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { Bot } from "lucide-react"
import { ChatMessageItem } from "./chat-message-item"
import type { ChatMessage } from "@/stores/chat-store"

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 h-5 px-1">
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "0ms" }} />
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "150ms" }} />
      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce-dot" style={{ animationDelay: "300ms" }} />
    </div>
  )
}

export function ChatMessageList({ messages, loading }: ChatMessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    measureElement: (el) => el.getBoundingClientRect().height,
    overscan: 5,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div
      ref={parentRef}
      className="flex-1 overflow-y-auto flex flex-col gap-5 pb-4 px-2"
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
  )
}

interface ChatMessageListProps {
  messages: ChatMessage[]
  loading: boolean
}
