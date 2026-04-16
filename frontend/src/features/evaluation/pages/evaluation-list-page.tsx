import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Card, List, Tabs, Tag } from "antd"

interface TaskItem {
  id: string
  name: string
  status: "pending" | "running" | "completed"
  model: string
}

interface DatasetItem {
  id: string
  name: string
  description: string
}

const mockTasks: TaskItem[] = [
  { id: "1", name: "MMLU Benchmark", status: "completed", model: "gpt-4" },
  { id: "2", name: "CEval Benchmark", status: "running", model: "qwen-72b" },
]

const mockDatasets: DatasetItem[] = [
  { id: "1", name: "mmlu-zh", description: "中文多任务语言理解数据集" },
  { id: "2", name: "ceval", description: "高级学科能力评估数据集" },
]

const statusColors = {
  pending: "default",
  running: "blue",
  completed: "green",
} as const

export default function EvaluationListPage() {
  const { t } = useTranslation("construct")
  const [activeTab, setActiveTab] = useState("tasks")

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mt-0 mb-6">{t("evaluation.title")}</h2>
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab={t("evaluation.tasks")} key="tasks">
          <div className="flex justify-end mb-4">
            <Button type="primary">{t("evaluation.create")}</Button>
          </div>
          <List
            dataSource={mockTasks}
            locale={{ emptyText: t("evaluation.emptyTasks") }}
            renderItem={(item) => (
              <List.Item className="bg-surface rounded-xl border border-border px-4 mb-3">
                <div className="flex items-center gap-4">
                  <div className="font-medium">{item.name}</div>
                  <Tag color={statusColors[item.status]}>
                    {t(`evaluation.${item.status}`)}
                  </Tag>
                  <span className="text-text-secondary text-sm">{item.model}</span>
                </div>
              </List.Item>
            )}
          />
        </Tabs.TabPane>

        <Tabs.TabPane tab={t("evaluation.datasets")} key="datasets">
          <div className="grid gap-4 sm:grid-cols-2">
            {mockDatasets.map((ds) => (
              <Card
                key={ds.id}
                title={ds.name}
                className="bg-surface border-border"
              >
                <p className="text-text-secondary text-sm m-0">
                  {ds.description}
                </p>
              </Card>
            ))}
            {mockDatasets.length === 0 && (
              <div className="text-text-secondary text-sm">
                {t("evaluation.emptyDatasets")}
              </div>
            )}
          </div>
        </Tabs.TabPane>
      </Tabs>
    </div>
  )
}
