import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tag } from "@/components/ui/tag"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  createEvaluationDataset,
  createEvaluationTask,
  deleteEvaluationDataset,
  deleteEvaluationTask,
  listEvaluationDatasets,
  listEvaluationTasks,
  updateEvaluationTask,
} from "@/services/evaluation"

const statusMap = {
  pending: "secondary",
  running: "info",
  completed: "success",
  failed: "destructive",
} as const

function statusVariant(status: string) {
  return statusMap[status as keyof typeof statusMap] || "outline"
}

export default function EvaluationListPage() {
  const { t } = useTranslation(["construct", "common"])
  const qc = useQueryClient()
  const [datasetForm, setDatasetForm] = useState({ name: "", description: "" })
  const [taskForm, setTaskForm] = useState({ name: "", model: "" })
  const tasksQuery = useQuery({ queryKey: ["evaluation", "tasks"], queryFn: listEvaluationTasks })
  const datasetsQuery = useQuery({ queryKey: ["evaluation", "datasets"], queryFn: listEvaluationDatasets })
  const tasks = tasksQuery.data?.items || []
  const datasets = datasetsQuery.data?.items || []

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["evaluation", "tasks"] })
    qc.invalidateQueries({ queryKey: ["evaluation", "datasets"] })
  }
  const createDatasetMutation = useMutation({
    mutationFn: createEvaluationDataset,
    onSuccess: () => {
      refresh()
      setDatasetForm({ name: "", description: "" })
    },
  })
  const createTaskMutation = useMutation({
    mutationFn: createEvaluationTask,
    onSuccess: () => {
      refresh()
      setTaskForm({ name: "", model: "" })
    },
  })
  const deleteDatasetMutation = useMutation({ mutationFn: deleteEvaluationDataset, onSuccess: refresh })
  const deleteTaskMutation = useMutation({ mutationFn: deleteEvaluationTask, onSuccess: refresh })
  const completeTaskMutation = useMutation({
    mutationFn: (id: string) => updateEvaluationTask(id, { status: "completed" }),
    onSuccess: refresh,
  })

  const createDataset = () => {
    if (!datasetForm.name.trim()) return
    createDatasetMutation.mutate(datasetForm)
  }
  const createTask = () => {
    if (!taskForm.name.trim() || datasets.length === 0) return
    createTaskMutation.mutate({
      name: taskForm.name,
      model: taskForm.model,
      dataset_id: datasets[0].id,
    })
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold mt-0 mb-6">{t("evaluation.title")}</h2>
      <Tabs defaultValue="tasks">
        <TabsList className="mb-4">
          <TabsTrigger value="tasks">{t("evaluation.tasks")}</TabsTrigger>
          <TabsTrigger value="datasets">{t("evaluation.datasets")}</TabsTrigger>
        </TabsList>

        <TabsContent value="tasks">
          <Card className="mb-4 grid gap-3 p-4 sm:grid-cols-[1fr_1fr_auto]">
            <Input
              value={taskForm.name}
              onChange={(e) => setTaskForm({ ...taskForm, name: e.target.value })}
              placeholder="Task name"
            />
            <Input
              value={taskForm.model}
              onChange={(e) => setTaskForm({ ...taskForm, model: e.target.value })}
              placeholder="Model"
            />
            <Button onClick={createTask} disabled={datasets.length === 0 || createTaskMutation.isPending}>
              {t("evaluation.create")}
            </Button>
          </Card>
          <div className="flex justify-end mb-4">
            <Button variant="outline" onClick={() => tasksQuery.refetch()} disabled={tasksQuery.isFetching}>
              {tasksQuery.isFetching
                ? t("status.loading", { ns: "common" })
                : t("actions.refresh", { ns: "common" })}
            </Button>
          </div>
          <div className="space-y-3">
            {tasks.map((item) => (
              <div key={item.id} className="bg-card rounded-xl border border-border px-4 py-3">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="font-medium">{item.name}</div>
                  <Tag variant={statusVariant(item.status)}>{t(`evaluation.${item.status}`, item.status)}</Tag>
                  <span className="text-muted-foreground text-sm">{item.model}</span>
                  <div className="ml-auto flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => completeTaskMutation.mutate(item.id)}>
                      Complete
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => deleteTaskMutation.mutate(item.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            {tasksQuery.isError && (
              <div className="text-destructive text-sm text-center py-8">{tasksQuery.error.message}</div>
            )}
            {!tasksQuery.isLoading && !tasksQuery.isError && tasks.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8">{t("evaluation.emptyTasks")}</div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="datasets">
          <Card className="mb-4 grid gap-3 p-4 sm:grid-cols-[1fr_1fr_auto]">
            <Input
              value={datasetForm.name}
              onChange={(e) => setDatasetForm({ ...datasetForm, name: e.target.value })}
              placeholder="Dataset name"
            />
            <Input
              value={datasetForm.description}
              onChange={(e) => setDatasetForm({ ...datasetForm, description: e.target.value })}
              placeholder="Description"
            />
            <Button onClick={createDataset} disabled={createDatasetMutation.isPending}>
              {t("actions.add", { ns: "common" })}
            </Button>
          </Card>
          <div className="grid gap-4 sm:grid-cols-2">
            {datasets.map((ds) => (
              <Card key={ds.id} className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="font-semibold mb-1">{ds.name}</h4>
                  <Button variant="destructive" size="sm" onClick={() => deleteDatasetMutation.mutate(ds.id)}>
                    Delete
                  </Button>
                </div>
                <p className="text-muted-foreground text-sm m-0">{ds.description || "-"}</p>
              </Card>
            ))}
            {datasetsQuery.isError && <div className="text-destructive text-sm">{datasetsQuery.error.message}</div>}
            {!datasetsQuery.isLoading && !datasetsQuery.isError && datasets.length === 0 && (
              <div className="text-muted-foreground text-sm text-center py-8 sm:col-span-2">
                {t("evaluation.emptyDatasets")}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
