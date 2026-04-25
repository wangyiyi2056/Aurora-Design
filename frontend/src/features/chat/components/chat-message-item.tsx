import { useState, Suspense, lazy } from "react"
import { User, Bot, Check, Copy } from "lucide-react"
import { useTranslation } from "react-i18next"
import { cn } from "@/lib/utils"

const MessageRenderer = lazy(() => import("./message-renderer"))

interface ChatMessageItemProps {
  role: "user" | "assistant" | "system"
  content: string
}

export function ChatMessageItem({ role, content }: ChatMessageItemProps) {
  const isUser = role === "user"
  const [copied, setCopied] = useState(false)
  const { t } = useTranslation("chat")

  if (role === "system") {
    return (
      <div className="text-center text-muted-foreground/50 text-[11px] py-2 tracking-wide uppercase">
        {content}
      </div>
    )
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div
      className={cn(
        "flex gap-3 group animate-message-fade-in",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] text-sm",
          isUser
            ? "gradient-avatar text-white shadow-lg shadow-blue-500/25 ring-1 ring-white/20"
            : "bg-muted/50 text-muted-foreground border border-border/40 ring-1 ring-white/[0.03]"
        )}
        aria-hidden="true"
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div className="relative max-w-[80%] flex flex-col">
        <div
          className={cn(
            "text-sm px-4 py-3 transition-all duration-200",
            isUser
              ? "user-bubble text-white rounded-[18px] rounded-tr-[6px] whitespace-pre-wrap"
              : "assistant-bubble text-foreground rounded-[18px] rounded-tl-[6px]"
          )}
        >
          {isUser ? content : (
            <Suspense fallback={<div className="text-muted-foreground">Loading content...</div>}>
              <MessageRenderer content={content} />
            </Suspense>
          )}
        </div>

        {/* Action bar */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-all duration-200 translate-y-0.5 group-hover:translate-y-0">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-muted-foreground/60 hover:text-foreground px-2 py-1 rounded-lg hover:bg-white/5 transition-all"
              aria-label={t("chat.copy")}
              title={t("chat.copy")}
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? t("chat.copied") : t("chat.copy")}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
