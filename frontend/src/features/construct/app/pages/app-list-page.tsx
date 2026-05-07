import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
import { createApp, listApps } from "@/services/apps"
import { listDatasources } from "@/services/database"
import { listKnowledge } from "@/services/knowledge"
import { listAgents, listSkillsDetail } from "@/services/models"

const appTypes = [
  { value: "chat", label: "Chat" },
  { value: "agent", label: "Agent" },
  { value: "rag", label: "RAG" },
]

interface FormData {
  name: string
  description: string
  type: string
  model: string
  knowledge_ids: string[]
  datasource_ids: string[]
  skill_names: string[]
}

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
}

export default function AppListPage() {
  const { t } = useTranslation("construct")
  const qc = useQueryClient()
  const appsQuery = useQuery({ queryKey: ["apps", "list"], queryFn: listApps })
  const agentsQuery = useQuery({ queryKey: ["agents", "list"], queryFn: listAgents })
  const knowledgeQuery = useQuery({ queryKey: ["knowledge", "list"], queryFn: listKnowledge })
  const datasourceQuery = useQuery({ queryKey: ["database", "datasources"], queryFn: listDatasources })
  const skillsQuery = useQuery({ queryKey: ["skills", "list"], queryFn: listSkillsDetail })
  const apps = appsQuery.data?.items || []
  const knowledgeBases = knowledgeQuery.data || []
  const datasources = datasourceQuery.data?.items || []
  const skills = skillsQuery.data?.skills || []
  const availableModels =
    agentsQuery.data?.agents
      .filter((agent) => agent.available)
      .map((agent) => ({ value: agent.id, label: agent.name })) || []
  const createMutation = useMutation({
    mutationFn: createApp,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps", "list"] }),
  })
  const [creating, setCreating] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)

  const [formData, setFormData] = useState<FormData>({
    name: "",
    description: "",
    type: "chat",
    model: availableModels[0]?.value || "codex",
    knowledge_ids: [],
    datasource_ids: [],
    skill_names: [],
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

  const handleSave = async () => {
    await createMutation.mutateAsync({
      ...formData,
      published: currentStep === 2,
    })
    setCreating(false)
    setCurrentStep(0)
    setFormData({
      name: "",
      description: "",
      type: "chat",
      model: "gpt-4",
      knowledge_ids: [],
      datasource_ids: [],
      skill_names: [],
    })
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
                  {item.knowledge_ids.length > 0 && (
                    <Tag variant="info">{t("app.knowledgeCount", { count: item.knowledge_ids.length })}</Tag>
                  )}
                  {item.datasource_ids.length > 0 && (
                    <Tag variant="success">{t("app.datasourceCount", { count: item.datasource_ids.length })}</Tag>
                  )}
                  {item.skill_names.length > 0 && (
                    <Tag variant="secondary">{t("app.skillCount", { count: item.skill_names.length })}</Tag>
                  )}
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
              <>
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
                      {availableModels.map((opt) => (
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

                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.knowledgeBindings")}</label>
                  <div className="flex flex-wrap gap-2">
                    {knowledgeBases.map((name) => (
                      <Button
                        key={name}
                        type="button"
                        variant={formData.knowledge_ids.includes(name) ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          setFormData({
                            ...formData,
                            knowledge_ids: toggleValue(formData.knowledge_ids, name),
                          })
                        }
                      >
                        {name}
                      </Button>
                    ))}
                    {knowledgeBases.length === 0 && (
                      <span className="text-sm text-muted-foreground">{t("app.noKnowledge")}</span>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.datasourceBindings")}</label>
                  <div className="flex flex-wrap gap-2">
                    {datasources.map((item) => (
                      <Button
                        key={item.name}
                        type="button"
                        variant={formData.datasource_ids.includes(item.name) ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          setFormData({
                            ...formData,
                            datasource_ids: toggleValue(formData.datasource_ids, item.name),
                          })
                        }
                      >
                        {item.name}
                      </Button>
                    ))}
                    {datasources.length === 0 && (
                      <span className="text-sm text-muted-foreground">{t("app.noDatasource")}</span>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("app.skillBindings")}</label>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((item) => (
                      <Button
                        key={item.name}
                        type="button"
                        variant={formData.skill_names.includes(item.name) ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          setFormData({
                            ...formData,
                            skill_names: toggleValue(formData.skill_names, item.name),
                          })
                        }
                      >
                        {item.name}
                      </Button>
                    ))}
                    {skills.length === 0 && (
                      <span className="text-sm text-muted-foreground">{t("app.noSkills")}</span>
                    )}
                  </div>
                </div>
              </>
            )}

            {currentStep === 2 && (
              <div className="space-y-3 py-4">
                <p className="text-muted-foreground text-sm">{t("app.reviewDesc")}</p>
                <div className="flex flex-wrap gap-2">
                  <Tag>{formData.type}</Tag>
                  <Tag variant="outline">{formData.model}</Tag>
                  <Tag variant="info">{t("app.knowledgeCount", { count: formData.knowledge_ids.length })}</Tag>
                  <Tag variant="success">{t("app.datasourceCount", { count: formData.datasource_ids.length })}</Tag>
                  <Tag variant="secondary">{t("app.skillCount", { count: formData.skill_names.length })}</Tag>
                </div>
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
