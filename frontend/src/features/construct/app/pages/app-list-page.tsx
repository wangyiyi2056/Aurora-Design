import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Card, Form, Input, List, Select, Steps, Tag } from "antd"
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

export default function AppListPage() {
  const { t } = useTranslation("construct")
  const [apps, setApps] = useState<AppItem[]>([
    { id: "1", name: "Data Analyst", description: "Analyze sales data", type: "chat", model: "gpt-4", published: true },
  ])
  const [creating, setCreating] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [form] = Form.useForm()

  const handleSave = async () => {
    const values = await form.validateFields()
    setApps((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        ...values,
        published: currentStep === 2,
      },
    ])
    setCreating(false)
    setCurrentStep(0)
    form.resetFields()
  }

  const steps = [
    { title: t("app.stepBasic"), key: "basic" },
    { title: t("app.stepConfig"), key: "config" },
    { title: t("app.stepPublish"), key: "publish" },
  ]

  return (
    <ConstructShell>
      {!creating ? (
        <>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold m-0">{t("app.title")}</h3>
            <Button type="primary" onClick={() => setCreating(true)}>
              {t("app.add")}
            </Button>
          </div>
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, lg: 3 }}
            dataSource={apps}
            locale={{ emptyText: t("app.empty") }}
            renderItem={(item) => (
              <List.Item>
                <Card
                  title={item.name}
                  className="bg-surface border-border w-full"
                  extra={item.published ? <Tag color="green">{t("app.published")}</Tag> : <Tag>{t("app.draft")}</Tag>}
                >
                  <p className="text-text-secondary text-sm m-0 mb-2">{item.description}</p>
                  <div className="flex flex-wrap gap-2">
                    <Tag>{item.type}</Tag>
                    <Tag>{item.model}</Tag>
                  </div>
                </Card>
              </List.Item>
            )}
          />
        </>
      ) : (
        <div className="max-w-2xl mx-auto bg-surface rounded-xl border border-border p-6">
          <Steps current={currentStep} items={steps} className="mb-6" />
          <Form form={form} layout="vertical">
            {currentStep === 0 && (
              <>
                <Form.Item
                  name="name"
                  label={t("app.name")}
                  rules={[{ required: true, message: t("app.requiredName") }]}
                >
                  <Input placeholder={t("app.name")} />
                </Form.Item>
                <Form.Item name="description" label={t("app.description")}>
                  <Input.TextArea placeholder={t("app.description")} rows={3} />
                </Form.Item>
                <Form.Item
                  name="type"
                  label={t("app.type")}
                  rules={[{ required: true }]}
                >
                  <Select options={appTypes} placeholder={t("app.type")} />
                </Form.Item>
              </>
            )}

            {currentStep === 1 && (
              <Form.Item
                name="model"
                label={t("app.model")}
                rules={[{ required: true }]}
              >
                <Select options={models} placeholder={t("app.selectModel")} />
              </Form.Item>
            )}

            {currentStep === 2 && (
              <div className="text-center py-8">
                <p className="text-text-secondary">{t("app.reviewDesc")}</p>
              </div>
            )}

            <div className="flex justify-between">
              <Button
                disabled={currentStep === 0}
                onClick={() => setCurrentStep((s) => s - 1)}
              >
                {t("app.back")}
              </Button>
              {currentStep < 2 ? (
                <Button
                  type="primary"
                  onClick={async () => {
                    if (currentStep === 0) {
                      await form.validateFields(["name", "type"])
                    }
                    setCurrentStep((s) => s + 1)
                  }}
                >
                  {t("app.next")}
                </Button>
              ) : (
                <Button type="primary" onClick={handleSave}>
                  {t("app.publish")}
                </Button>
              )}
            </div>
          </Form>
        </div>
      )}
    </ConstructShell>
  )
}
