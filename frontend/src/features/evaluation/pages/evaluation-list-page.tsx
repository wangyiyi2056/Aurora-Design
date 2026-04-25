import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tag } from "@/components/ui/tag"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"

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

const statusMap = {
  pending: "secondary",
  running: "info",
  completed: "success",
} as const

export default function EvaluationListPage() {
  const { t } = useTranslation("construct")

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mt-0 mb-6">{t("evaluation.title")}</h2>
      <Tabs defaultValue="tasks">
        <TabsList className="mb-4">
          <TabsTrigger value="tasks">{t("evaluation.tasks")}</TabsTrigger>
          <TabsTrigger value="datasets">{t("evaluation.datasets")}</TabsTrigger>
        </TabsList>

        <TabsContent value="tasks">
          <div className="flex justify-end mb-4">
            <Button>{t("evaluation.create")}</Button>
          </div>
          <div className="space-y-3">
            {mockTasks.map((item) => (
              <div
                key={item.id}
                className="bg-card rounded-xl border border-border px-4 py-3"
              >
                <div className="flex items-center gap-4">
                  <div className="font-medium">{item.name}</div>
                  <Tag variant={statusMap[item.status]}>
                    {t(`evaluation.${item.status}`)}
                  </Tag>
                  <span className="text-muted-foreground text-sm">{item.model}</span>
                </div>
              </div>
            ))}
            {mockTasks.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8">
                {t("evaluation.emptyTasks")}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="datasets">
          <div className="grid gap-4 sm:grid-cols-2">
            {mockDatasets.map((ds) => (
              <Card key={ds.id} className="p-4">
                <h4 className="font-semibold mb-1">{ds.name}</h4>
                <p className="text-muted-foreground text-sm m-0">
                  {ds.description}
                </p>
              </Card>
            ))}
            {mockDatasets.length === 0 && (
              <div className="text-muted-foreground text-sm">
                {t("evaluation.emptyDatasets")}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
