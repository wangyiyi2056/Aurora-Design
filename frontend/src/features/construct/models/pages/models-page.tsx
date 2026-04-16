import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Form, Input, Modal, Select, Table, Tag, message } from "antd"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { useModelsStore, type ModelItem } from "@/stores/models-store"
import { testModelConnection } from "@/services/model-test"

const modelTypes = [
  { value: "llm", label: "LLM" },
  { value: "embedding", label: "Embedding" },
  { value: "rerank", label: "Rerank" },
]

export default function ModelsPage() {
  const { t } = useTranslation(["construct", "common"])
  const { models, addModel, updateModel, removeModel } = useModelsStore()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [testingId, setTestingId] = useState<string | null>(null)

  const handleAdd = async () => {
    const values = await form.validateFields()
    addModel({
      name: values.name,
      type: values.type,
      baseUrl: values.baseUrl,
      apiKey: values.apiKey,
    })
    setIsModalOpen(false)
    form.resetFields()
    message.success(t("models.addSuccess"))
  }

  const handleTest = async (item: ModelItem) => {
    setTestingId(item.id)
    updateModel(item.id, { status: "testing" })
    try {
      await testModelConnection(item.baseUrl, item.apiKey)
      updateModel(item.id, { status: "available", statusMessage: undefined })
      message.success(t("models.testSuccess"))
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("models.testFailed")
      updateModel(item.id, { status: "error", statusMessage: msg })
      message.error(t("models.testFailed"))
    } finally {
      setTestingId(null)
    }
  }

  const columns = [
    {
      title: t("models.name"),
      dataIndex: "name",
      key: "name",
    },
    {
      title: t("models.type"),
      dataIndex: "type",
      key: "type",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: t("models.baseUrl"),
      dataIndex: "baseUrl",
      key: "baseUrl",
      ellipsis: true,
    },
    {
      title: t("models.status"),
      key: "status",
      render: (_: unknown, item: ModelItem) => {
        if (item.status === "testing" || testingId === item.id) {
          return <Tag color="processing">{t("models.testing")}</Tag>
        }
        if (item.status === "available") {
          return <Tag color="success">{t("models.available")}</Tag>
        }
        if (item.status === "error") {
          return (
            <Tag color="error" title={item.statusMessage}>
              {t("models.error")}
            </Tag>
          )
        }
        return <Tag>{t("models.untested")}</Tag>
      },
    },
    {
      title: t("models.actions"),
      key: "actions",
      render: (_: unknown, item: ModelItem) => (
        <div className="flex gap-2">
          <Button
            size="small"
            loading={testingId === item.id}
            onClick={() => handleTest(item)}
          >
            {t("models.test")}
          </Button>
          <Button
            size="small"
            danger
            type="link"
            onClick={() => removeModel(item.id)}
          >
            {t("actions.delete", { ns: "common" })}
          </Button>
        </div>
      ),
    },
  ]

  return (
    <ConstructShell>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold m-0">{t("models.title")}</h3>
        <Button type="primary" onClick={() => setIsModalOpen(true)}>
          {t("models.add")}
        </Button>
      </div>

      <Table
        dataSource={models}
        columns={columns}
        rowKey="id"
        pagination={false}
      />

      <Modal
        title={t("models.add")}
        open={isModalOpen}
        onOk={handleAdd}
        onCancel={() => {
          setIsModalOpen(false)
          form.resetFields()
        }}
        okText={t("actions.add", { ns: "common" })}
        cancelText={t("actions.cancel", { ns: "common" })}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item
            name="name"
            label={t("models.name")}
            rules={[{ required: true, message: t("models.nameRequired") }]}
          >
            <Input placeholder="e.g. gemma-4-e4b-it-8bit" />
          </Form.Item>
          <Form.Item
            name="type"
            label={t("models.type")}
            rules={[{ required: true }]}
            initialValue="llm"
          >
            <Select options={modelTypes} />
          </Form.Item>
          <Form.Item
            name="baseUrl"
            label={t("models.baseUrl")}
            rules={[{ required: true, message: t("models.baseUrlRequired") }]}
            initialValue="http://127.0.0.1:8000/v1"
          >
            <Input placeholder="http://127.0.0.1:8000/v1" />
          </Form.Item>
          <Form.Item
            name="apiKey"
            label={t("models.apiKey")}
            rules={[{ required: true, message: t("models.apiKeyRequired") }]}
          >
            <Input.Password placeholder="sk-xxx" />
          </Form.Item>
        </Form>
      </Modal>
    </ConstructShell>
  )
}
