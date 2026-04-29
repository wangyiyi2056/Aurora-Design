import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"
import { Edit, Trash2, Plug, Plus, Loader2 } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tag } from "@/components/ui/tag"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createModelConfig,
  deleteModelConfig,
  listModelConfigs,
  testSavedModelConnection,
  updateModelConfig,
  type ModelItem,
} from "@/services/models"

const modelTypes = [
  { value: "llm", label: "LLM (OpenAI Compatible)" },
  { value: "anthropic", label: "LLM (Anthropic)" },
  { value: "embedding", label: "Embedding" },
  { value: "rerank", label: "Rerank" },
]

interface FormData {
  name: string
  type: string
  baseUrl: string
  apiKey: string
}

export default function ModelsPage() {
  const { t } = useTranslation(["construct", "common"])
  const qc = useQueryClient()
  const modelsQuery = useQuery({
    queryKey: ["models", "list"],
    queryFn: listModelConfigs,
  })
  const models = modelsQuery.data?.items || []
  const invalidateModels = () => qc.invalidateQueries({ queryKey: ["models", "list"] })
  const createMutation = useMutation({ mutationFn: createModelConfig, onSuccess: invalidateModels })
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateModelConfig>[1] }) =>
      updateModelConfig(id, payload),
    onSuccess: invalidateModels,
  })
  const deleteMutation = useMutation({ mutationFn: deleteModelConfig, onSuccess: invalidateModels })
  const testMutation = useMutation({ mutationFn: testSavedModelConnection, onSuccess: invalidateModels })
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<ModelItem | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState<string | null>(null)

  const [formData, setFormData] = useState<FormData>({
    name: "",
    type: "llm",
    baseUrl: "http://127.0.0.1:8000/v1",
    apiKey: "123456",
  })

  const [formErrors, setFormErrors] = useState<Record<string, string>>({})

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) errors.name = t("models.nameRequired")
    if (!formData.baseUrl.trim()) errors.baseUrl = t("models.baseUrlRequired")
    if (!editingModel && !formData.apiKey.trim()) errors.apiKey = t("models.apiKeyRequired")
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleAdd = async () => {
    if (!validateForm()) return
    await createMutation.mutateAsync({
      name: formData.name,
      type: formData.type,
      base_url: formData.baseUrl,
      api_key: formData.apiKey,
    })
    setIsModalOpen(false)
    resetForm()
    toast.success(t("models.addSuccess"))
  }

  const handleEdit = async () => {
    if (!editingModel) return
    if (!validateForm()) return
    await updateMutation.mutateAsync({
      id: editingModel.id,
      payload: {
      name: formData.name,
      type: formData.type,
      base_url: formData.baseUrl,
      ...(formData.apiKey.trim() && !formData.apiKey.includes("...")
        ? { api_key: formData.apiKey }
        : {}),
      },
    })
    setIsModalOpen(false)
    setEditingModel(null)
    resetForm()
    toast.success(t("models.editSuccess"))
  }

  const openEditModal = (item: ModelItem) => {
    setEditingModel(item)
    setFormData({
      name: item.name,
      type: item.type,
      baseUrl: item.baseUrl,
      apiKey: "",
    })
    setFormErrors({})
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingModel(null)
    resetForm()
  }

  const resetForm = () => {
    setFormData({
      name: "",
      type: "llm",
      baseUrl: "http://127.0.0.1:8000/v1",
      apiKey: "123456",
    })
    setFormErrors({})
  }

  const handleTest = async (item: ModelItem) => {
    setTestingId(item.id)
    try {
      await testMutation.mutateAsync(item.id)
      toast.success(t("models.testSuccess"))
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("models.testFailed")
      toast.error(msg)
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id)
    setDeleteConfirmOpen(null)
  }

  const getStatusTag = (item: ModelItem) => {
    if (item.status === "testing" || testingId === item.id) {
      return <Tag variant="info">{t("models.testing")}</Tag>
    }
    if (item.status === "available") {
      return <Tag variant="success">{t("models.available")}</Tag>
    }
    if (item.status === "error") {
      return (
        <Tag variant="warning" title={item.statusMessage}>
          {t("models.error")}
        </Tag>
      )
    }
    return <Tag variant="secondary">{t("models.untested")}</Tag>
  }

  return (
    <ConstructShell>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold m-0">{t("models.title")}</h3>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          {t("models.add")}
        </Button>
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("models.name")}</TableHead>
              <TableHead className="w-[160px]">{t("models.type")}</TableHead>
              <TableHead>{t("models.baseUrl")}</TableHead>
              <TableHead className="w-[100px]">{t("models.status")}</TableHead>
              <TableHead className="w-[200px]">{t("models.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell>
                  <Tag variant={item.type === "anthropic" ? "info" : "default"}>
                    {modelTypes.find((m) => m.value === item.type)?.label || item.type}
                  </Tag>
                </TableCell>
                <TableCell className="text-muted-foreground truncate max-w-[200px]">
                  {item.baseUrl}
                </TableCell>
                <TableCell>{getStatusTag(item)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => openEditModal(item)}>
                      <Edit className="h-4 w-4 mr-1" />
                      {t("actions.edit", { ns: "common" })}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={testingId === item.id}
                      onClick={() => handleTest(item)}
                    >
                      {testingId === item.id ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <Plug className="h-4 w-4 mr-1" />
                      )}
                      {t("models.test")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteConfirmOpen(item.id)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      {t("actions.delete", { ns: "common" })}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {models.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  {t("models.empty") || "暂无模型"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingModel ? t("models.edit") : t("models.add")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("models.name")}</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g. gpt-4o-mini"
              />
              {formErrors.name && (
                <p className="text-sm text-destructive">{formErrors.name}</p>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("models.type")}</label>
              <Select
                value={formData.type}
                onValueChange={(v) => setFormData({ ...formData, type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {modelTypes.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("models.baseUrl")}</label>
              <Input
                value={formData.baseUrl}
                onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                placeholder="http://127.0.0.1:8000/v1"
              />
              {formErrors.baseUrl && (
                <p className="text-sm text-destructive">{formErrors.baseUrl}</p>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("models.apiKey")}</label>
              <Input
                type="password"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                placeholder="sk-xxx"
              />
              {formErrors.apiKey && (
                <p className="text-sm text-destructive">{formErrors.apiKey}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeModal}>
              {t("actions.cancel", { ns: "common" })}
            </Button>
            <Button onClick={editingModel ? handleEdit : handleAdd}>
              {editingModel ? t("actions.save", { ns: "common" }) : t("actions.add", { ns: "common" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteConfirmOpen !== null}
        onOpenChange={(open: boolean) => !open && setDeleteConfirmOpen(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("actions.delete", { ns: "common" })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("models.deleteConfirm") || "确定要删除此模型吗？"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {t("actions.cancel", { ns: "common" })}
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteConfirmOpen && handleDelete(deleteConfirmOpen)}>
              {t("actions.delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConstructShell>
  )
}
