import { useMemo, useRef } from "react"
import ReactMarkdown from "react-markdown"
import {
  CheckCircle2,
  Circle,
  Clock3,
  Code2,
  Download,
  Eye,
  FileText,
  Loader2,
  Monitor,
  PlayCircle,
  RefreshCw,
  Share2,
  Table2,
  TerminalSquare,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import type {
  ReactAgentArtifact,
  ReactAgentOutput,
  ReactAgentPanelView,
  ReactAgentSnapshot,
  ReactAgentStep,
} from "@/features/chat/utils/react-agent-workspace"

interface ReactAgentWorkspaceProps {
  userQuestion: string
  snapshot: ReactAgentSnapshot
  artifacts: ReactAgentArtifact[]
  panelView: ReactAgentPanelView
  onPanelViewChange: (view: ReactAgentPanelView) => void
  loading: boolean
  inputArea: React.ReactNode
  onRerun?: () => void
  onShare?: () => void
}

const stepIconMap: Record<ReactAgentStep["type"], React.ReactNode> = {
  read: <FileText className="h-4 w-4" />,
  skill: <PlayCircle className="h-4 w-4" />,
  sql: <TerminalSquare className="h-4 w-4" />,
  html: <Code2 className="h-4 w-4" />,
  code: <Code2 className="h-4 w-4" />,
  other: <Circle className="h-4 w-4" />,
}

function statusIcon(status: ReactAgentStep["status"]) {
  if (status === "completed") return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
  if (status === "error") return <Circle className="h-3.5 w-3.5 text-red-500" />
  if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
  return <Clock3 className="h-3.5 w-3.5 text-muted-foreground" />
}

function StepCard({
  step,
  active,
  outputs,
}: {
  step: ReactAgentStep
  active: boolean
  outputs: ReactAgentOutput[]
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-background px-4 py-3 transition-colors",
        active && "border-blue-400 shadow-sm",
        step.status === "error" && "border-red-300",
        step.status === "completed" && !active && "border-border"
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground",
            step.type === "skill" && "bg-violet-50 text-violet-600",
            step.type === "sql" && "bg-blue-50 text-blue-600",
            step.type === "html" && "bg-orange-50 text-orange-600",
            step.type === "read" && "bg-slate-50 text-slate-600"
          )}
        >
          {stepIconMap[step.type]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {step.action && (
              <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600">
                {step.action}
              </span>
            )}
            <h3 className="truncate text-sm font-semibold text-foreground">{step.title}</h3>
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {step.detail || "Thought/Action/Observation"}
          </p>
        </div>
        {statusIcon(step.status)}
      </div>
      {outputs.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5 pl-11">
          {outputs.map((output, index) => (
            <span
              key={`${output.output_type}-${index}`}
              className="rounded border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {output.output_type}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function OutputPreview({ output }: { output: ReactAgentOutput }) {
  if (output.output_type === "code") {
    const content =
      typeof output.content === "string"
        ? output.content
        : JSON.stringify(output.content, null, 2)
    return (
      <pre className="overflow-auto rounded-lg border bg-slate-950 p-3 text-xs text-slate-100">
        <code>{content}</code>
      </pre>
    )
  }
  if (output.output_type === "json" || output.output_type === "table" || output.output_type === "chart") {
    return (
      <pre className="overflow-auto rounded-lg border bg-muted/40 p-3 text-xs text-foreground">
        <code>{JSON.stringify(output.content, null, 2)}</code>
      </pre>
    )
  }
  if (output.output_type === "html") {
    const value = output.content as { title?: string } | string
    return (
      <div className="rounded-lg border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
        HTML artifact ready: {typeof value === "string" ? "Report.html" : value.title || "Report.html"}
      </div>
    )
  }
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
      {typeof output.content === "string" ? output.content : JSON.stringify(output.content)}
    </div>
  )
}

export function ReactAgentWorkspace({
  userQuestion,
  snapshot,
  artifacts,
  panelView,
  onPanelViewChange,
  loading,
  inputArea,
  onRerun,
  onShare,
}: ReactAgentWorkspaceProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const htmlArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.type === "html"),
    [artifacts]
  )
  const activeStep = snapshot.steps.find((step) => step.id === snapshot.activeStepId) || snapshot.steps.at(-1)
  const outputCount = Object.values(snapshot.outputs).reduce((sum, outputs) => sum + outputs.length, 0)

  const printReport = () => {
    iframeRef.current?.contentWindow?.focus()
    iframeRef.current?.contentWindow?.print()
  }

  const downloadReport = () => {
    if (!htmlArtifact) return
    const blob = new Blob([String(htmlArtifact.content || "")], { type: "text/html;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = htmlArtifact.name || "Report.html"
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex h-[calc(100vh-48px)] min-h-0 w-full overflow-hidden bg-background">
      <aside className="flex min-w-[360px] basis-[40%] flex-col border-r bg-white">
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <div className="mb-5 flex justify-end">
            <div className="max-w-[78%] rounded-2xl bg-muted px-4 py-3 text-sm font-medium text-foreground">
              {userQuestion}
            </div>
          </div>

          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            执行步骤
          </div>

          <div className="space-y-3">
            {snapshot.steps.length === 0 && (
              <div className="rounded-lg border bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
                正在准备分析链路...
              </div>
            )}
            {snapshot.steps.map((step) => (
              <StepCard
                key={step.id}
                step={step}
                active={step.id === snapshot.activeStepId && loading}
                outputs={snapshot.outputs[step.id] || []}
              />
            ))}
          </div>

          {snapshot.summary && (
            <div className="prose prose-sm mt-6 max-w-none text-foreground">
              <ReactMarkdown>{snapshot.summary}</ReactMarkdown>
            </div>
          )}
        </div>
        <div className="px-8 pb-3">{inputArea}</div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col bg-white">
        <div className="flex h-12 shrink-0 items-center justify-between border-b px-5">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-red-500" />
              <span className="h-3 w-3 rounded-full bg-yellow-400" />
              <span className="h-3 w-3 rounded-full bg-green-500" />
            </div>
            <Monitor className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">DB-GPT 的电脑</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" onClick={printReport} disabled={!htmlArtifact}>
              <Download className="h-3.5 w-3.5" />
              导出 PDF
            </Button>
            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" onClick={downloadReport} disabled={!htmlArtifact}>
              <FileText className="h-3.5 w-3.5" />
              下载 HTML
            </Button>
            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" onClick={onRerun} disabled={!onRerun}>
              <RefreshCw className="h-3.5 w-3.5" />
              重新执行
            </Button>
            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs text-blue-600" onClick={onShare} disabled={!onShare}>
              <Share2 className="h-3.5 w-3.5" />
              分享
            </Button>
          </div>
        </div>

        <Tabs value={panelView} onValueChange={(value) => onPanelViewChange(value as ReactAgentPanelView)} className="flex min-h-0 flex-1 flex-col">
          <div className="h-10 shrink-0 border-b px-5">
            <TabsList className="h-10 rounded-none bg-transparent p-0">
              <TabsTrigger value="execution" className="h-10 rounded-none border-b-2 border-transparent px-4 data-[state=active]:border-foreground data-[state=active]:shadow-none">
                执行步骤
              </TabsTrigger>
              <TabsTrigger value="files" className="h-10 rounded-none border-b-2 border-transparent px-4 data-[state=active]:border-foreground data-[state=active]:shadow-none">
                任务文件
                {artifacts.length > 0 && <span className="ml-2 rounded-full bg-muted px-1.5 text-[10px]">{artifacts.length}</span>}
              </TabsTrigger>
              <TabsTrigger value="summary" className="h-10 rounded-none border-b-2 border-transparent px-4 data-[state=active]:border-foreground data-[state=active]:shadow-none">
                摘要
              </TabsTrigger>
              <TabsTrigger value="html-preview" disabled={!htmlArtifact} className="h-10 rounded-none border-b-2 border-transparent px-4 data-[state=active]:border-foreground data-[state=active]:shadow-none">
                <Eye className="mr-1.5 h-3.5 w-3.5" />
                {htmlArtifact?.name || "Report.html"}
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="execution" className="m-0 min-h-0 flex-1 overflow-auto p-5">
            <div className="space-y-3">
              {snapshot.steps.map((step) => (
                <div key={step.id} className="rounded-lg border p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="font-semibold">{step.title}</div>
                    {statusIcon(step.status)}
                  </div>
                  <div className="text-xs text-muted-foreground">{step.detail || step.action || step.id}</div>
                  <div className="mt-3 space-y-2">
                    {(snapshot.outputs[step.id] || []).map((output, index) => (
                      <OutputPreview key={`${step.id}-${output.output_type}-${index}`} output={output} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="files" className="m-0 min-h-0 flex-1 overflow-auto p-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {artifacts.map((artifact) => (
                <button
                  key={artifact.id}
                  type="button"
                  className="rounded-lg border p-4 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/40"
                  onClick={() => {
                    if (artifact.type === "html") onPanelViewChange("html-preview")
                    if (artifact.type === "summary") onPanelViewChange("summary")
                  }}
                >
                  <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
                    {artifact.type === "html" ? <Eye className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
                  </div>
                  <div className="truncate text-sm font-semibold">{artifact.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{artifact.type}</div>
                </button>
              ))}
              {artifacts.length === 0 && (
                <div className="col-span-full rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                  暂无任务文件
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="summary" className="m-0 min-h-0 flex-1 overflow-auto p-6">
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{snapshot.summary || "分析摘要生成中..."}</ReactMarkdown>
            </div>
          </TabsContent>

          <TabsContent value="html-preview" className="m-0 min-h-0 flex-1 bg-white">
            {htmlArtifact ? (
              <iframe
                ref={iframeRef}
                title={htmlArtifact.name}
                srcDoc={String(htmlArtifact.content || "")}
                sandbox="allow-scripts allow-same-origin"
                className="h-full w-full border-0 bg-white"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Report.html 生成中...
              </div>
            )}
          </TabsContent>
        </Tabs>

        <div className="flex h-7 shrink-0 items-center justify-between border-t px-5 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full", loading ? "bg-blue-500" : "bg-emerald-500")} />
            {loading ? "运行中" : "就绪"}
          </span>
          <span>{outputCount} 个输出</span>
          <span>Step ID: {activeStep?.id || "-"}</span>
        </div>
      </section>
    </div>
  )
}
