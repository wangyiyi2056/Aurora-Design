import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AtSign, Plus, Settings2, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createPrompt,
  deletePrompt,
  getSystemPrompt,
  listCustomPrompts,
  saveSystemPrompt,
  type PromptPayload,
} from "@/services/prompts"

const emptyCustomPrompt: PromptPayload = {
  name: "",
  category: "general",
  template: "",
  variables: [],
  version: 1,
  enabled: true,
  description: "",
}

function previewText(value: string, max = 120) {
  const text = value.replace(/\s+/g, " ").trim()
  return text.length > max ? `${text.slice(0, max)}...` : text
}

export default function PromptPage() {
  const qc = useQueryClient()
  const systemQuery = useQuery({ queryKey: ["prompts", "system"], queryFn: getSystemPrompt })
  const customQuery = useQuery({ queryKey: ["prompts", "custom"], queryFn: listCustomPrompts })
  const [systemPrompt, setSystemPrompt] = useState("")
  const [customForm, setCustomForm] = useState<PromptPayload>(emptyCustomPrompt)
  const [customDialogOpen, setCustomDialogOpen] = useState(false)
  const [systemSaved, setSystemSaved] = useState(false)
  const customPrompts = customQuery.data?.items || []

  useEffect(() => {
    if (systemQuery.data) setSystemPrompt(systemQuery.data.template || "")
  }, [systemQuery.data])

  const saveSystemMutation = useMutation({
    mutationFn: saveSystemPrompt,
    onSuccess: (data) => {
      qc.setQueryData(["prompts", "system"], data)
      setSystemSaved(true)
      window.setTimeout(() => setSystemSaved(false), 1600)
    },
  })

  const createCustomMutation = useMutation({
    mutationFn: createPrompt,
    onSuccess: (created) => {
      qc.setQueryData<{ items: typeof customPrompts }>(["prompts", "custom"], (current) => ({
        items: [created, ...(current?.items || []).filter((item) => item.id !== created.id)],
      }))
      qc.invalidateQueries({ queryKey: ["prompts", "custom"] })
      setCustomForm(emptyCustomPrompt)
      setCustomDialogOpen(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deletePrompt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts", "custom"] }),
  })

  const saveCustom = () => {
    if (!customForm.name.trim() || !customForm.template.trim()) return
    createCustomMutation.mutate({
      ...customForm,
      name: customForm.name.trim(),
      template: customForm.template.trim(),
      description: customForm.description?.trim() || "",
      variables: [],
      enabled: true,
    })
  }

  return (
    <ConstructShell>
      <Tabs defaultValue="system" className="space-y-4">
        <TabsList>
          <TabsTrigger value="system">系统提示词</TabsTrigger>
          <TabsTrigger value="custom">自定义提示词</TabsTrigger>
        </TabsList>

        <TabsContent value="system">
          <Card className="overflow-hidden">
            <div className="flex items-start justify-between gap-4 border-b bg-muted/20 px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Settings2 className="h-4 w-4 text-muted-foreground" />
                  <h3 className="m-0 text-base font-semibold">系统提示词</h3>
                  <Tag variant="outline">全局生效</Tag>
                </div>
                <p className="m-0 mt-1 text-sm text-muted-foreground">
                  保存后会自动加入所有对话的系统上下文。
                </p>
              </div>
              <div className="shrink-0 text-right text-xs text-muted-foreground">
                {systemPrompt.trim().length} 字符
              </div>
            </div>
            <div className="space-y-4 p-5">
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="输入全局系统提示词"
                rows={10}
                className="min-h-[280px] resize-y font-mono text-sm leading-6"
                data-testid="system-prompt-textarea"
              />
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">
                  适合放置所有对话都应遵循的身份、风格和安全边界。
                </span>
                <div className="flex items-center gap-3">
                  {systemSaved ? <span className="text-sm text-muted-foreground">已保存</span> : null}
                  {saveSystemMutation.isError ? (
                    <span className="text-sm text-destructive">保存失败</span>
                  ) : null}
                  <Button
                    onClick={() => saveSystemMutation.mutate(systemPrompt)}
                    disabled={saveSystemMutation.isPending}
                  >
                    保存系统提示词
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="custom">
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <AtSign className="h-4 w-4 text-muted-foreground" />
                  <h3 className="m-0 text-base font-semibold">自定义提示词</h3>
                  <Tag variant="outline">{customPrompts.length} 条</Tag>
                </div>
                <p className="m-0 mt-1 text-sm text-muted-foreground">
                  管理可在聊天输入框中通过 @ 引用的提示词。
                </p>
              </div>
              <Button onClick={() => setCustomDialogOpen(true)}>
                <Plus className="h-4 w-4" />
                新增提示词
              </Button>
            </div>

            <Card className="overflow-hidden">
              {customPrompts.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableHead className="w-[220px]">名称</TableHead>
                      <TableHead className="w-[220px]">描述</TableHead>
                      <TableHead>提示词预览</TableHead>
                      <TableHead className="w-[100px] text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {customPrompts.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="font-medium text-foreground">{item.name}</span>
                            <Tag variant="outline">{item.category}</Tag>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          <span className="block max-w-[220px] truncate">
                            {item.description || "-"}
                          </span>
                        </TableCell>
                        <TableCell>
                          <code className="block max-w-[760px] truncate rounded-md bg-muted/50 px-2.5 py-1.5 text-xs text-muted-foreground">
                            {previewText(item.template) || "-"}
                          </code>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => deleteMutation.mutate(item.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                            删除
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
              {customQuery.isLoading ? (
                <div className="py-12 text-center text-sm text-muted-foreground">加载中...</div>
              ) : null}
              {!customQuery.isLoading && customPrompts.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 py-14 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                    <AtSign className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">暂无自定义提示词</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      点击右上角新增，之后可在聊天输入框通过 @ 引用。
                    </div>
                  </div>
                </div>
              ) : null}
            </Card>

            <Dialog open={customDialogOpen} onOpenChange={setCustomDialogOpen}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>新增自定义提示词</DialogTitle>
                  <DialogDescription>
                    保存后可在聊天输入框通过 @ 引用。
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <Input
                    value={customForm.name}
                    onChange={(e) => setCustomForm({ ...customForm, name: e.target.value })}
                    placeholder="名称"
                  />
                  <Textarea
                    value={customForm.description}
                    onChange={(e) => setCustomForm({ ...customForm, description: e.target.value })}
                    placeholder="描述"
                    rows={2}
                  />
                  <Textarea
                    value={customForm.template}
                    onChange={(e) => setCustomForm({ ...customForm, template: e.target.value })}
                    placeholder="提示词内容"
                    rows={8}
                    className="font-mono text-sm leading-6"
                  />
                  {createCustomMutation.isError ? (
                    <span className="text-sm text-destructive">新增失败</span>
                  ) : null}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCustomDialogOpen(false)}>
                    取消
                  </Button>
                  <Button onClick={saveCustom} disabled={createCustomMutation.isPending}>
                    保存提示词
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </TabsContent>
      </Tabs>
    </ConstructShell>
  )
}
