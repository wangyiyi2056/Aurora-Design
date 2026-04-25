import { useState } from "react"
import { VisChart } from "./vis-chart"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface DashboardChartItem {
  sql?: string
  type: string
  title?: string
  describe?: string
  data: Record<string, unknown>[]
  err_msg?: string | null
}

interface VisDashboardProps {
  charts: DashboardChartItem[]
  title?: string
}

type LayoutMode = "grid" | "row" | "compact"

const LAYOUT_OPTIONS = [
  { value: "grid", label: "网格布局" },
  { value: "row", label: "单列布局" },
  { value: "compact", label: "紧凑布局" },
]

export function VisDashboard({ charts, title }: VisDashboardProps) {
  const [layout, setLayout] = useState<LayoutMode>("grid")

  if (!charts || charts.length === 0) {
    return (
      <div className="my-2 rounded-xl border border-border bg-card p-4">
        <div className="text-sm text-muted-foreground">暂无图表数据</div>
      </div>
    )
  }

  const successCharts = charts.filter((c) => !c.err_msg)
  const errorCharts = charts.filter((c) => c.err_msg)

  const getGridClass = () => {
    switch (layout) {
      case "grid":
        return "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-2"
      case "row":
        return "flex flex-col gap-4"
      case "compact":
        return "grid grid-cols-1 gap-2 md:grid-cols-3 lg:grid-cols-4"
      default:
        return "grid grid-cols-1 gap-4 md:grid-cols-2"
    }
  }

  return (
    <div className="my-2 rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex justify-between items-center px-4 py-3 border-b border-border bg-muted flex-wrap gap-2">
        <div>
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          <span className="text-sm text-muted-foreground">
            {successCharts.length} 个图表
            {errorCharts.length > 0 && ` · ${errorCharts.length} 个错误`}
          </span>
        </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Select value={layout} onValueChange={(v) => setLayout(v as LayoutMode)}>
                <SelectTrigger className="w-[120px] h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LAYOUT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </TooltipTrigger>
            <TooltipContent>布局模式</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {errorCharts.length > 0 && (
        <div className="px-4 py-2 bg-muted border-b border-border">
          {errorCharts.map((chart, idx) => (
            <div key={idx} className="text-sm text-destructive mb-1">
              {chart.title || `图表 ${idx + 1}`}: {chart.err_msg}
            </div>
          ))}
        </div>
      )}

      <div className={`p-4 ${getGridClass()}`}>
        {successCharts.map((chart, idx) => (
          <div
            key={idx}
            className={`rounded-lg border border-border bg-muted overflow-hidden ${
              layout === "compact" ? "p-2" : "p-3"
            }`}
          >
            <VisChart
              data={chart.data}
              type={chart.type}
              title={chart.title || `图表 ${idx + 1}`}
              sql={chart.sql}
              describe={chart.describe}
            />
          </div>
        ))}
      </div>

      {successCharts.length > 4 && layout === "grid" && (
        <div className="px-4 py-2 text-center text-sm text-muted-foreground bg-muted border-t border-border">
          提示: 切换到紧凑布局可查看更多图表
        </div>
      )}
    </div>
  )
}