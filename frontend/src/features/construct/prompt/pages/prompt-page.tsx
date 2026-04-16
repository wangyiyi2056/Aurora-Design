import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Input, List, Tag, Form } from "antd"
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
        <div className="lg:col-span-1 bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold m-0">{t("prompt.title")}</h3>
            <Button
              type="primary"
              size="small"
              onClick={() => {
                setSelected(null)
                setName("")
                setContent("")
              }}
            >
              {t("prompt.add")}
            </Button>
          </div>
          <List
            dataSource={prompts}
            locale={{ emptyText: t("prompt.empty") }}
            renderItem={(item) => (
              <List.Item
                className={`cursor-pointer rounded px-2 transition-colors ${
                  selected?.id === item.id ? "bg-primary/10" : "hover:bg-surface-hover"
                }`}
                onClick={() => handleSelect(item)}
                actions={[
                  <Button
                    key="del"
                    type="link"
                    danger
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(item.id)
                    }}
                  >
                    {t("prompt.delete")}
                  </Button>,
                ]}
              >
                <div className="font-medium text-sm">{item.name}</div>
              </List.Item>
            )}
          />
        </div>

        <div className="lg:col-span-2 bg-surface rounded-xl border border-border p-4">
          <Form layout="vertical">
            <Form.Item label={t("prompt.name")}>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("prompt.name")}
              />
            </Form.Item>
            <Form.Item label={t("prompt.content")}>
              <Input.TextArea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={t("prompt.placeholder")}
                rows={8}
              />
            </Form.Item>
            {variables.length > 0 && (
              <Form.Item label={t("prompt.variables")}>
                <div className="flex flex-wrap gap-2">
                  {variables.map((v) => (
                    <Tag key={v} color="blue">
                      {v}
                    </Tag>
                  ))}
                </div>
              </Form.Item>
            )}
            {content && (
              <Form.Item label={t("prompt.preview")}>
                <div className="bg-bg p-3 rounded text-sm whitespace-pre-wrap border border-border">
                  {previewText}
                </div>
              </Form.Item>
            )}
            <Button type="primary" onClick={handleSave} disabled={!name.trim() || !content.trim()}>
              {t("prompt.save")}
            </Button>
          </Form>
        </div>
      </div>
    </ConstructShell>
  )
}
