import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createPrompt,
  deletePrompt,
  listPrompts,
  renderPrompt,
  type PromptPayload,
} from "@/services/prompts"

const emptyPrompt: PromptPayload = {
  name: "",
  category: "general",
  template: "Question: {{question}}",
  variables: ["question"],
  version: 1,
  enabled: true,
  description: "",
}

export default function PromptPage() {
  const qc = useQueryClient()
  const promptsQuery = useQuery({ queryKey: ["prompts", "list"], queryFn: () => listPrompts() })
  const [form, setForm] = useState<PromptPayload>(emptyPrompt)
  const [previewId, setPreviewId] = useState("")
  const [preview, setPreview] = useState("")
  const prompts = promptsQuery.data?.items || []

  const createMutation = useMutation({
    mutationFn: createPrompt,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", "list"] })
      setForm(emptyPrompt)
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deletePrompt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts", "list"] }),
  })
  const renderMutation = useMutation({
    mutationFn: async (id: string) => renderPrompt(id, { question: "Top sales by region" }),
    onSuccess: (data) => setPreview(data.content),
  })

  const save = () => {
    if (!form.name.trim() || !form.template.trim()) return
    createMutation.mutate({
      ...form,
      variables: String(form.variables || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    })
  }

  return (
    <ConstructShell>
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="p-4 space-y-3">
          <h3 className="m-0 text-base font-semibold">Prompt Templates</h3>
          <Input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
          />
          <Input
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            placeholder="Category"
          />
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description"
            rows={2}
          />
          <Textarea
            value={form.template}
            onChange={(e) => setForm({ ...form, template: e.target.value })}
            placeholder="Template"
            rows={7}
          />
          <Input
            value={(form.variables || []).join(",")}
            onChange={(e) => setForm({ ...form, variables: e.target.value.split(",") })}
            placeholder="Variables, comma separated"
          />
          <Button onClick={save} disabled={createMutation.isPending}>
            Add Prompt
          </Button>
        </Card>

        <div className="space-y-3">
          {prompts.map((item) => (
            <Card key={item.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="m-0 font-semibold">{item.name}</h4>
                    <Tag variant="outline">{item.category}</Tag>
                    <Tag variant={item.enabled ? "success" : "secondary"}>v{item.version}</Tag>
                  </div>
                  <p className="m-0 mt-2 text-sm text-muted-foreground">{item.description || "-"}</p>
                  <pre className="mt-3 max-h-32 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">
                    {item.template}
                  </pre>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setPreviewId(item.id)
                      renderMutation.mutate(item.id)
                    }}
                  >
                    Render
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate(item.id)}>
                    Delete
                  </Button>
                </div>
              </div>
              {previewId === item.id && preview && (
                <div className="mt-3 rounded-md border bg-card p-3 text-sm">{preview}</div>
              )}
            </Card>
          ))}
          {prompts.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">No prompts yet</div>
          )}
        </div>
      </div>
    </ConstructShell>
  )
}
