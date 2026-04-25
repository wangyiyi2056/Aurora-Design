import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"

interface PromptItem {
  id: string
  name: string
  content: string
}

function extractVariables(content: string): string[] {
  const matches = content.match(/\{\{(\w+)\}\}/g)
  if (!matches) return []
  return Array.from(new Set(matches.map((m) => m.slice(2, -2))))
}

export default function PromptPage() {
  const { t } = useTranslation("construct")
  const [prompts, setPrompts] = useState<PromptItem[]>([
    { id: "1", name: "SQL Expert", content: "You are a SQL expert. Please write a query for {{table}}." },
  ])
  const [selected, setSelected] = useState<PromptItem | null>(null)
  const [name, setName] = useState("")
  const [content, setContent] = useState("")

  const variables = extractVariables(content)

  const handleSelect = (item: PromptItem) => {
    setSelected(item)
    setName(item.name)
    setContent(item.content)
  }

  const handleSave = () => {
    if (!name.trim() || !content.trim()) return
    if (selected) {
      setPrompts((prev) =>
        prev.map((p) => (p.id === selected.id ? { ...p, name, content } : p))
      )
    } else {
      setPrompts((prev) => [...prev, { id: Date.now().toString(), name, content }])
    }
    setSelected(null)
    setName("")
    setContent("")
  }

  const handleDelete = (id: string) => {
    setPrompts((prev) => prev.filter((p) => p.id !== id))
    if (selected?.id === id) {
      setSelected(null)
      setName("")
      setContent("")
    }
  }

  const previewText = variables.reduce((text, v) => {
    return text.replace(new RegExp(`\\{\\{${v}\\}\\}`, "g"), `[${v}]`)
  }, content)

  return (
    <ConstructShell>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-card rounded-xl border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold m-0">{t("prompt.title")}</h3>
            <Button
              size="sm"
              onClick={() => {
                setSelected(null)
                setName("")
                setContent("")
              }}
            >
              {t("prompt.add")}
            </Button>
          </div>
          <div className="space-y-1">
            {prompts.map((item) => (
              <div
                key={item.id}
                className={`flex items-center justify-between px-2 py-2 rounded cursor-pointer transition-colors ${
                  selected?.id === item.id ? "bg-primary/10" : "hover:bg-muted"
                }`}
                onClick={() => handleSelect(item)}
              >
                <div className="font-medium text-sm">{item.name}</div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-destructive"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(item.id)
                  }}
                >
                  {t("prompt.delete")}
                </Button>
              </div>
            ))}
            {prompts.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-4">
                {t("prompt.empty")}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2 bg-card rounded-xl border border-border p-4 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">{t("prompt.name")}</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("prompt.name")}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">{t("prompt.content")}</label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={t("prompt.placeholder")}
              rows={8}
            />
          </div>
          {variables.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("prompt.variables")}</label>
              <div className="flex flex-wrap gap-2">
                {variables.map((v) => (
                  <Tag key={v} variant="info">
                    {v}
                  </Tag>
                ))}
              </div>
            </div>
          )}
          {content && (
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("prompt.preview")}</label>
              <div className="bg-background p-3 rounded text-sm whitespace-pre-wrap border border-border">
                {previewText}
              </div>
            </div>
          )}
          <Button onClick={handleSave} disabled={!name.trim() || !content.trim()}>
            {t("prompt.save")}
          </Button>
        </div>
      </div>
    </ConstructShell>
  )
}
