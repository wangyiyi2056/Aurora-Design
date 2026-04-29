import { Paperclip, Zap, BookOpen, Database, ChevronUp, Loader2, Plus, ChevronDown, Check, Square } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { useTranslation } from "react-i18next"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { listModelConfigs } from "@/services/models"

interface ChatAttachmentTag {
  type: "file" | "skill" | "knowledge" | "database"
  name: string
}

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  loading: boolean
  streaming?: boolean
  onAbort?: () => void
  attachments?: ChatAttachmentTag[]
  onRemoveAttachment?: (index: number) => void
  onAttachFile?: () => void
  onUseSkill?: () => void
  onUseKnowledge?: () => void
  onUseDatabase?: () => void
  model: string
  onModelChange: (model: string) => void
}

const builtinModels = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4o", label: "GPT-4o" },
]

export function ChatInput({
  value,
  onChange,
  onSend,
  loading,
  streaming,
  onAbort,
  attachments,
  onRemoveAttachment,
  onAttachFile,
  onUseSkill,
  onUseKnowledge,
  onUseDatabase,
  model,
  onModelChange,
}: ChatInputProps) {
  const { t } = useTranslation("chat")
  const { data: modelsData } = useQuery({
    queryKey: ["models", "list"],
    queryFn: listModelConfigs,
    staleTime: 30_000,
  })
  const models = modelsData?.items || []

  const customModels = models
    .filter((m) => (m.type === "llm" || m.type === "anthropic") && m.status === "available")
    .map((m) => ({
      value: m.name,
      label: m.type === "anthropic" ? `${m.name} (Anthropic)` : m.name
    }))

  const getModelMeta = (value: string) => {
    const lower = value.toLowerCase()
    if (lower.includes("gpt")) return { color: "#10a37f", label: "OpenAI" }
    if (lower.includes("claude") || lower.includes("anthropic")) return { color: "#cc785c", label: "Anthropic" }
    if (lower.includes("kimi")) return { color: "#6c5ce7", label: "Kimi" }
    if (lower.includes("gemma") || lower.includes("llama") || lower.includes("mistral") || lower.includes("qwen")) return { color: "#a78bfa", label: "Open" }
    return { color: "#00c6ff", label: "LLM" }
  }

  const modelOptions = [...customModels, ...builtinModels]
  const activeMeta = getModelMeta(model)
  const activeLabel = modelOptions.find((o) => o.value === model)?.label || model

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const getAttachmentIcon = (type: string) => {
    switch (type) {
      case "file":
        return <Paperclip className="h-3 w-3" />
      case "skill":
        return <Zap className="h-3 w-3" />
      case "knowledge":
        return <BookOpen className="h-3 w-3" />
      case "database":
        return <Database className="h-3 w-3" />
      default:
        return null
    }
  }

  return (
    <div className="chat-input-float pt-8 pb-3 px-2 -mt-16 relative z-10">
      <div className="input-glass rounded-2xl px-4 py-3">
        <Textarea
          className="bg-transparent border-0 shadow-none focus-visible:ring-0 resize-none text-[15px] min-h-[24px] max-h-[200px] py-1 placeholder:text-muted-foreground/40 leading-relaxed"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("chat.placeholder")}
          disabled={loading}
          aria-label={t("chat.placeholder")}
          rows={1}
        />
        {attachments && attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {attachments.map((att, idx) => (
              <Tag
                key={`${att.type}-${idx}`}
                variant="secondary"
                closable
                onClose={() => onRemoveAttachment?.(idx)}
                className="text-xs flex items-center gap-1"
              >
                {getAttachmentIcon(att.type)}
                {att.name}
              </Tag>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between mt-3">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Tools Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-1.5 h-7 pl-2.5 pr-2.5 text-xs rounded-full bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] hover:border-white/[0.14] transition-all duration-200 text-muted-foreground hover:text-foreground group/tools">
                  <Plus className="h-3.5 w-3.5" />
                  <span className="font-medium">{t("chat.addTool")}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56 rounded-xl p-1.5 gap-0">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/50 px-2 py-1 font-medium">
                  Tools
                </DropdownMenuLabel>
                <DropdownMenuItem
                  onClick={() => onAttachFile?.()}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs"
                >
                  <Paperclip className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="flex-1 truncate">{t("chat.attachFile")}</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={onUseSkill}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs"
                >
                  <Zap className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="flex-1 truncate">{t("chat.useSkill")}</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={onUseKnowledge}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs"
                >
                  <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="flex-1 truncate">{t("chat.useKnowledge")}</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={onUseDatabase}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs"
                >
                  <Database className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="flex-1 truncate">{t("chat.useDatabase")}</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Model Selector */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 h-7 pl-2.5 pr-2 text-xs rounded-full bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] hover:border-white/[0.14] transition-all duration-200 group/select">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: activeMeta.color, boxShadow: `0 0 6px ${activeMeta.color}40` }}
                  />
                  <span className="text-foreground/90 font-medium truncate max-w-[140px]">{activeLabel}</span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground/50 group-hover/select:text-muted-foreground transition-colors" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56 rounded-xl p-1.5 gap-0">
                {customModels.length > 0 && (
                  <>
                    <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/50 px-2 py-1 font-medium">
                      Custom Models
                    </DropdownMenuLabel>
                    {customModels.map((opt) => {
                      const meta = getModelMeta(opt.value)
                      const isActive = opt.value === model
                      return (
                        <DropdownMenuItem
                          key={opt.value}
                          onClick={() => onModelChange(opt.value)}
                          className={cn(
                            "flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs",
                            isActive && "bg-primary/10 text-primary"
                          )}
                        >
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: meta.color }}
                          />
                          <span className="flex-1 truncate">{opt.label}</span>
                          {isActive && <Check className="h-3.5 w-3.5 text-primary" />}
                        </DropdownMenuItem>
                      )
                    })}
                  </>
                )}
                {customModels.length > 0 && <DropdownMenuSeparator className="my-1 bg-border/40" />}
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/50 px-2 py-1 font-medium">
                  Built-in
                </DropdownMenuLabel>
                {builtinModels.map((opt) => {
                  const meta = getModelMeta(opt.value)
                  const isActive = opt.value === model
                  return (
                    <DropdownMenuItem
                      key={opt.value}
                      onClick={() => onModelChange(opt.value)}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-2 py-1.5 cursor-pointer text-xs",
                        isActive && "bg-primary/10 text-primary"
                      )}
                    >
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: meta.color }}
                      />
                      <span className="flex-1 truncate">{opt.label}</span>
                      {isActive && <Check className="h-3.5 w-3.5 text-primary" />}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {streaming && onAbort ? (
            <Button
              variant="destructive"
              size="icon"
              onClick={onAbort}
              aria-label={t("chat.stop")}
              className="rounded-full h-9 w-9 bg-red-500 hover:bg-red-600 border-0 shadow-lg shadow-red-500/20"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="default"
              size="icon"
              onClick={onSend}
              disabled={!value.trim() || loading}
              aria-label={t("chat.send")}
              className="rounded-full h-9 w-9 gradient-btn border-0 shadow-lg shadow-blue-500/20"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
      </div>
      <div className="text-center mt-2">
        <span className="text-[10px] text-muted-foreground/40 tracking-wide">
          Enter to send, Shift+Enter for new line
        </span>
      </div>
    </div>
  )
}
