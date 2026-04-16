import { useState, Suspense, lazy } from "react"
import { UserOutlined, RobotOutlined, CheckOutlined, CopyOutlined } from "@ant-design/icons"
import { useTranslation } from "react-i18next"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

const MessageRenderer = lazy(() => import("./message-renderer"))

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

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
      <div className="text-center text-text-secondary text-xs py-2">
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
        "flex gap-3 group",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm",
          isUser ? "bg-primary text-white" : "bg-surface-elevated text-text-secondary"
        )}
        aria-hidden="true"
      >
        {isUser ? <UserOutlined /> : <RobotOutlined />}
      </div>
      <div className="relative max-w-[80%]">
        <div
          className={cn(
            "text-sm px-4 py-3 rounded-xl",
            isUser
              ? "bg-primary text-white rounded-tr-sm whitespace-pre-wrap"
              : "bg-surface-elevated text-text rounded-tl-sm border border-border"
          )}
        >
          {isUser ? content : (
            <Suspense fallback={<div className="text-text-secondary">Loading content...</div>}>
              <MessageRenderer content={content} />
            </Suspense>
          )}
        </div>
        {!isUser && (
          <button
            onClick={handleCopy}
            className="absolute -bottom-6 left-0 flex items-center gap-1 text-xs text-text-secondary opacity-0 transition-opacity group-hover:opacity-100 hover:text-text"
            aria-label={t("chat.copy")}
            title={t("chat.copy")}
          >
            {copied ? <CheckOutlined /> : <CopyOutlined />}
            {copied ? t("chat.copied") : t("chat.copy")}
          </button>
        )}
      </div>
    </div>
  )
}
