/**
 * Debug Pipeline Panel
 *
 * Displays the Excel analysis pipeline steps with status tracking.
 * Each conversation resets the state.
 */

import { useChatStore } from "@/stores/chat-store"
import { Check, X, Loader2, Circle, FileSpreadsheet, Upload, Database, Brain, ArrowRightLeft, MessageSquare, Code, BarChart3, Send } from "lucide-react"
import { cn } from "@/lib/utils"

export interface PipelineStep {
  id: string
  name: string
  description: string
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  timestamp?: number
  duration?: number
  detail?: string
}

const PIPELINE_STEPS: PipelineStep[] = [
  { id: "select_excel", name: "选择 Excel", description: "用户选择文件", status: "pending" },
  { id: "upload_file", name: "前端上传", description: "上传文件到服务器", status: "pending" },
  { id: "store_file", name: "存储文件", description: "后端保存文件", status: "pending" },
  { id: "create_duckdb", name: "创建 DuckDB", description: "初始化内存数据库", status: "pending" },
  { id: "learn_structure", name: "学习结构", description: "LLM 分析数据结构", status: "pending" },
  { id: "transform_columns", name: "列名转换", description: "标准化列名", status: "pending" },
  { id: "user_question", name: "用户提问", description: "接收用户查询", status: "pending" },
  { id: "generate_sql", name: "生成 SQL", description: "LLM 生成查询语句", status: "pending" },
  { id: "execute_sql", name: "执行 SQL", description: "DuckDB 执行查询", status: "pending" },
  { id: "render_visualization", name: "可视化渲染", description: "生成图表数据", status: "pending" },
  { id: "return_frontend", name: "返回前端", description: "渲染完成", status: "pending" },
]

const STEP_ICONS: Record<string, React.ReactNode> = {
  select_excel: <FileSpreadsheet className="h-4 w-4" />,
  upload_file: <Upload className="h-4 w-4" />,
  store_file: <FileSpreadsheet className="h-4 w-4" />,
  create_duckdb: <Database className="h-4 w-4" />,
  learn_structure: <Brain className="h-4 w-4" />,
  transform_columns: <ArrowRightLeft className="h-4 w-4" />,
  user_question: <MessageSquare className="h-4 w-4" />,
  generate_sql: <Code className="h-4 w-4" />,
  execute_sql: <Database className="h-4 w-4" />,
  render_visualization: <BarChart3 className="h-4 w-4" />,
  return_frontend: <Send className="h-4 w-4" />,
}

const STATUS_COLORS: Record<string, string> = {
  pending: "text-muted-foreground bg-muted/30",
  running: "text-blue-500 bg-blue-500/10 border-blue-500/30",
  completed: "text-green-500 bg-green-500/10 border-green-500/30",
  failed: "text-red-500 bg-red-500/10 border-red-500/30",
  skipped: "text-amber-500 bg-amber-500/10 border-amber-500/30",
}

const STATUS_BG_COLORS: Record<string, string> = {
  pending: "bg-muted/20",
  running: "bg-blue-500/5",
  completed: "bg-green-500/5",
  failed: "bg-red-500/5",
  skipped: "bg-amber-500/5",
}

interface DebugPipelinePanelProps {
  className?: string
}

export function DebugPipelinePanel({ className }: DebugPipelinePanelProps) {
  const { debugPipelineSteps, debugPipelineEnabled } = useChatStore()

  if (!debugPipelineEnabled) return null

  // Merge default steps with current state
  const steps = PIPELINE_STEPS.map((defaultStep) => {
    const currentStep = debugPipelineSteps.find((s) => s.id === defaultStep.id)
    return currentStep || defaultStep
  })

  // Calculate progress
  const completedCount = steps.filter((s) => s.status === "completed").length
  const failedCount = steps.filter((s) => s.status === "failed").length
  const runningCount = steps.filter((s) => s.status === "running").length
  const progress = Math.round((completedCount / steps.length) * 100)

  return (
    <div className={cn("rounded-xl border border-border/40 bg-surface/50 backdrop-blur-sm p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground/80 flex items-center gap-2">
          <Brain className="h-4 w-4" />
          Excel 分析流程
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{progress}%</span>
          <div className="w-24 h-1.5 bg-muted/30 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-300",
                failedCount > 0 ? "bg-red-500" : "bg-green-500"
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-1">
        {steps.map((step, index) => {
          const Icon = STEP_ICONS[step.id] || <Circle className="h-4 w-4" />
          const isLast = index === steps.length - 1

          return (
            <div key={step.id} className="flex items-center">
              {/* Step item */}
              <div
                className={cn(
                  "flex items-center gap-2 py-1.5 px-2 rounded-lg transition-all duration-200 flex-1",
                  STATUS_BG_COLORS[step.status],
                  step.status === "running" && "animate-pulse"
                )}
              >
                {/* Status icon */}
                <div className={cn("w-5 h-5 rounded-full flex items-center justify-center", STATUS_COLORS[step.status])}>
                  {step.status === "completed" && <Check className="h-3 w-3" />}
                  {step.status === "failed" && <X className="h-3 w-3" />}
                  {step.status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
                  {step.status === "pending" && <Circle className="h-3 w-3 opacity-30" />}
                  {step.status === "skipped" && <Circle className="h-3 w-3" />}
                </div>

                {/* Step icon */}
                <div className="text-muted-foreground">{Icon}</div>

                {/* Step name */}
                <span className={cn(
                  "text-xs font-medium",
                  step.status === "completed" && "text-green-600",
                  step.status === "failed" && "text-red-600",
                  step.status === "running" && "text-blue-600",
                  step.status === "pending" && "text-muted-foreground",
                )}>
                  {step.name}
                </span>

                {/* Duration */}
                {step.duration && step.status === "completed" && (
                  <span className="text-xs text-muted-foreground ml-auto">
                    {step.duration}ms
                  </span>
                )}

                {/* Detail */}
                {step.detail && (
                  <span className="text-xs text-muted-foreground truncate max-w-[100px]">
                    {step.detail}
                  </span>
                )}
              </div>

              {/* Connector line */}
              {!isLast && (
                <div className={cn(
                  "w-px h-4 mx-1",
                  step.status === "completed" ? "bg-green-500/30" : "bg-border/30"
                )} />
              )}
            </div>
          )
        })}
      </div>

      {/* Summary */}
      <div className="mt-3 pt-3 border-t border-border/20 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Check className="h-3 w-3 text-green-500" />
          {completedCount} 完成
        </span>
        {failedCount > 0 && (
          <span className="flex items-center gap-1">
            <X className="h-3 w-3 text-red-500" />
            {failedCount} 失败
          </span>
        )}
        {runningCount > 0 && (
          <span className="flex items-center gap-1">
            <Loader2 className="h-3 w-3 text-blue-500 animate-spin" />
            {runningCount} 进行中
          </span>
        )}
      </div>
    </div>
  )
}