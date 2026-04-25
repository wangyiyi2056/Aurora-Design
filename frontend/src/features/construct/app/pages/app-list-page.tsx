import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tag } from "@/components/ui/tag"
import { Steps } from "@/components/ui/steps"
import { ConstructShell } from "@/features/construct/components/construct-shell"

interface AppItem {
  id: string
  name: string
  description: string
  type: string
  model: string
  published: boolean
}

const appTypes = [
  { value: "chat", label: "Chat" },
  { value: "agent", label: "Agent" },
  { value: "rag", label: "RAG" },
]

const models = [
  { value: "gpt-4", label: "GPT-4" },
  { value: "gpt-3.5", label: "GPT-3.5" },
  { value: "local", label: "Local Model" },
]

interface FormData {
  name: string
  description: string
  type: string
  model: string
}

export default function AppListPage() {
  const { t } = useTranslation("construct")
  const [apps, setApps] = useState<AppItem[]>([
    { id: "1", name: "Data Analyst", description: "Analyze sales data", type: "chat", model: "gpt-4", published: true },
  ])
  const [creating, setCreating] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)

  const [formData, setFormData] = useState<FormData>({
    name: "",
    description: "",
    type: "chat",
    model: "gpt-4",
  })

  const [formErrors, setFormErrors] = useState<Record<string, string>>({})

  const validateBasic = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) errors.name = t("app.requiredName")
    if (!formData.type) errors.type = t("app.requiredType")
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const validateModel = (): boolean => {
    const errors: Record<string, string> = {}
    if (!formData.model) errors.model = t("app.requiredModel")
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSave = () => {
    setApps((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        ...formData,
        published: currentStep === 2,
      },
    ])
    setCreating(false)
    setCurrentStep(0)
    setFormData({ name: "", description: "", type: "chat", model: "gpt-4" })
    setFormErrors({})
  }

  const steps = [
    { title: t("app.stepBasic"), key: "basic" },
    { title: t("app.stepConfig"), key: "config" },
    { title: t("app.stepPublish"), key: "publish" },
  ]

  const handleNext = () => {
    if (currentStep === 0 && !validateBasic()) return
    if (currentStep === 1 && !validateModel()) return
    setCurrentStep((s) => s + 1)
  }

  return (
    <ConstructShell>
      {!creating ? (
        <>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold m-0">{t("app.title")}</h3>
            <Button onClick={() => setCreating(true)}>
              {t("app.add")}
            </Button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {apps.map((item) => (
              <Card key={item.id} className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">{item.name}</h4>
                  {item.published ? (
                    <Tag variant="success">{t("app.published")}</Tag>
                  ) : (
                    <Tag variant="secondary">{t("app.draft")}</Tag>
                  )}
                </div>
                <p className="text-muted-foreground text-sm m-0 mb-2">{item.description}</p>
                <div className="flex flex-wrap gap-2">
                  <Tag>{item.type}</Tag>
                  <Tag variant="outline">{item.model}</Tag>
                </div>
              </Card>
            ))}
            {apps.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8 col-span-full">
                {t("app.empty")}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="max-w-2xl mx-auto bg-card rounded-xl border border-border p-6">
          <Steps steps={steps} current={currentStep} className="mb-6" />
          <div className="space-y-4">
            {currentStep === 0 && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.name")}</label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder={t("app.name")}
                  />
                  {formErrors.name && (
                    <p className="text-sm text-destructive">{formErrors.name}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.description")}</label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder={t("app.description")}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.type")}</label>
                  <Select
                    value={formData.type}
                    onValueChange={(v) => setFormData({ ...formData, type: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {appTypes.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {formErrors.type && (
                    <p className="text-sm text-destructive">{formErrors.type}</p>
                  )}
                </div>
              </>
            )}

            {currentStep === 1 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("app.model")}</label>
                <Select
                  value={formData.model}
                  onValueChange={(v) => setFormData({ ...formData, model: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {models.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.model && (
                  <p className="text-sm text-destructive">{formErrors.model}</p>
                )}
              </div>
            )}

            {currentStep === 2 && (
              <div className="text-center py-8">
                <p className="text-muted-foreground">{t("app.reviewDesc")}</p>
              </div>
            )}

            <div className="flex justify-between pt-4">
              <Button
                variant="outline"
                disabled={currentStep === 0}
                onClick={() => setCurrentStep((s) => s - 1)}
              >
                {t("app.back")}
              </Button>
              {currentStep < 2 ? (
                <Button onClick={handleNext}>
                  {t("app.next")}
                </Button>
              ) : (
                <Button onClick={handleSave}>
                  {t("app.publish")}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </ConstructShell>
  )
}
