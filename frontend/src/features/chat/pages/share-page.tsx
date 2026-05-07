import { useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { ReactAgentWorkspace } from "@/features/chat/components/react-agent-workspace"
import type {
  ReactAgentArtifact,
  ReactAgentPanelView,
  ReactAgentSnapshot,
} from "@/features/chat/utils/react-agent-workspace"

interface SharedAgentReport {
  type: "react-agent-report"
  id: string
  question: string
  snapshot: ReactAgentSnapshot
  artifacts: ReactAgentArtifact[]
  createdAt: number
}

function readSharedReport(id?: string): SharedAgentReport | null {
  if (!id) return null
  try {
    const raw = localStorage.getItem(`chatbi-share-${id}`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SharedAgentReport
    return parsed?.type === "react-agent-report" ? parsed : null
  } catch {
    return null
  }
}

export default function SharePage() {
  const { id } = useParams()
  const report = useMemo(() => readSharedReport(id), [id])
  const [panelView, setPanelView] = useState<ReactAgentPanelView>(
    report?.artifacts.some((artifact) => artifact.type === "html") ? "html-preview" : "summary"
  )

  if (!report) {
    return (
      <div className="mx-auto flex h-[calc(100vh-48px)] max-w-3xl flex-col items-center justify-center px-6 text-center">
        <h1 className="text-xl font-semibold">分享内容不存在</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          这个分享保存在当前浏览器本地，换设备或清理缓存后将无法读取。
        </p>
      </div>
    )
  }

  return (
    <ReactAgentWorkspace
      userQuestion={report.question}
      snapshot={report.snapshot}
      artifacts={report.artifacts}
      panelView={panelView}
      onPanelViewChange={setPanelView}
      loading={false}
      inputArea={
        <div className="rounded-2xl border bg-muted/30 px-4 py-3 text-center text-xs text-muted-foreground">
          只读分享视图
        </div>
      }
    />
  )
}
