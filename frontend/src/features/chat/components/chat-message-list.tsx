import { useEffect, useRef } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { ChatMessageItem } from "./chat-message-item"
import type { ChatMessage } from "@/stores/chat-store"

interface ChatMessageListProps {
  messages: ChatMessage[]
  loading: boolean
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
      className="flex-1 overflow-y-auto flex flex-col gap-4 pb-4 px-2"
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
        <div className="flex gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-elevated text-text-secondary text-sm">
            ...
          </div>
          <div className="bg-surface-elevated text-text text-sm px-4 py-3 rounded-xl rounded-tl-sm border border-border">
            Thinking...
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
