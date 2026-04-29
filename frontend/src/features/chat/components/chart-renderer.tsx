import { useState, useMemo } from "react"
import ReactECharts from "echarts-for-react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import { BarChart3, Code, Table, AlertCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

export interface ChartRendererProps {
  data: {
    type: string // chart type: bar, line, pie, scatter, response_table, etc.
    sql?: string // SQL query that generated the data
    data?: Record<string, unknown>[] // raw data array
    config?: Record<string, unknown> // additional chart configuration
  }
  className?: string
  loading?: boolean
  error?: string | null
}

type ChartType = "bar" | "line" | "pie" | "scatter" | "response_table" | "area" | "radar" | "gauge"

export function normalizeChartType(type: string): ChartType {
  const normalized = type.toLowerCase().replace("-", "_")
  const responseTypeMap: Record<string, ChartType> = {
    response_bar_chart: "bar",
    response_line_chart: "line",
    response_pie_chart: "pie",
    response_scatter_chart: "scatter",
    response_area_chart: "area",
    response_donut_chart: "pie",
    response_table: "response_table",
    response_bubble_chart: "scatter",
  }
  if (responseTypeMap[normalized]) {
    return responseTypeMap[normalized]
  }
  if (normalized.startsWith("response_")) {
    return "response_table"
  }
  if (["bar", "line", "pie", "scatter", "area", "radar", "gauge", "response_table"].includes(normalized)) {
    return normalized as ChartType
  }
  // Default fallback
  return "bar"
}

function generateEChartsOption(chartType: ChartType, rawData: Record<string, unknown>[]): Record<string, unknown> {
  if (!rawData || rawData.length === 0) {
    return {}
  }

  // Ensure first row has data keys
  const firstRow = rawData[0]
  const keys = Object.keys(firstRow)
  if (keys.length === 0) {
    return {}
  }

  const xKey = keys[0] // First column as x-axis/category
  const yKeys = keys.slice(1) // Remaining columns as values

  const categories = rawData.map((item) => String(item[xKey] ?? ""))
  const seriesData = yKeys.map((key) => rawData.map((item) => Number(item[key]) || 0))

  const baseOption = {
    tooltip: {
      trigger: chartType === "pie" ? "item" : "axis",
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "rgba(255, 255, 255, 0.1)",
      textStyle: { color: "#fff" },
    },
    legend: {
      show: yKeys.length > 1,
      top: 10,
      textStyle: { color: "#94a3b8" },
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "3%",
      top: yKeys.length > 1 ? 60 : 40,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8", fontSize: 12 },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 12 },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
  }

  switch (chartType) {
    case "bar":
      return {
        ...baseOption,
        series: yKeys.map((key, idx) => ({
          name: key,
          type: "bar",
          data: seriesData[idx],
          barMaxWidth: 40,
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
            color: getSeriesColor(idx),
          },
        })),
      }

    case "line":
      return {
        ...baseOption,
        series: yKeys.map((key, idx) => ({
          name: key,
          type: "line",
          data: seriesData[idx],
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { width: 2, color: getSeriesColor(idx) },
          itemStyle: { color: getSeriesColor(idx) },
        })),
      }

    case "area":
      return {
        ...baseOption,
        series: yKeys.map((key, idx) => ({
          name: key,
          type: "line",
          data: seriesData[idx],
          smooth: true,
          symbol: "none",
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: getSeriesColor(idx, 0.4) },
                { offset: 1, color: getSeriesColor(idx, 0.05) },
              ],
            },
          },
          lineStyle: { width: 2, color: getSeriesColor(idx) },
        })),
      }

    case "scatter":
      return {
        ...baseOption,
        xAxis: { ...baseOption.xAxis, type: "value" },
        yAxis: { ...baseOption.yAxis },
        series: yKeys.map((key, idx) => ({
          name: key,
          type: "scatter",
          data: rawData.map((item) => [Number(item[xKey]) || 0, Number(item[key]) || 0]),
          symbolSize: 8,
          itemStyle: { color: getSeriesColor(idx) },
        })),
      }

    case "pie":
      const pieData = rawData.map((item) => ({
        name: String(item[xKey] ?? ""),
        value: Number(item[yKeys[0]]) || 0,
      }))
      return {
        tooltip: {
          trigger: "item",
          formatter: "{b}: {c} ({d}%)",
          backgroundColor: "rgba(15, 23, 42, 0.9)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          textStyle: { color: "#fff" },
        },
        legend: {
          orient: "vertical",
          right: 10,
          top: "center",
          textStyle: { color: "#94a3b8" },
        },
        series: [
          {
            type: "pie",
            radius: ["40%", "70%"],
            center: ["40%", "50%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 6,
              borderColor: "#0f172a",
              borderWidth: 2,
            },
            label: { show: false },
            emphasis: {
              label: { show: true, fontSize: 14, fontWeight: "bold" },
            },
            data: pieData.map((item, idx) => ({
              ...item,
              itemStyle: { color: getSeriesColor(idx) },
            })),
          },
        ],
      }

    case "radar":
      const radarIndicators = keys.map((key) => ({
        name: key,
        max: Math.max(...rawData.map((item) => Number(item[key]) || 0)) * 1.2 || 100,
      }))
      return {
        tooltip: { trigger: "item" },
        radar: {
          indicator: radarIndicators,
          axisName: { color: "#94a3b8" },
          splitLine: { lineStyle: { color: "#1e293b" } },
          splitArea: { areaStyle: { color: ["rgba(30, 41, 59, 0.3)", "rgba(30, 41, 59, 0.1)"] } },
        },
        series: [
          {
            type: "radar",
            data: rawData.map((item, idx) => ({
              name: String(item[xKey] ?? ""),
              value: keys.map((k) => Number(item[k]) || 0),
              areaStyle: { color: getSeriesColor(idx, 0.3) },
            })),
          },
        ],
      }

    case "gauge":
      const gaugeValue = rawData.length > 0 ? Number(rawData[0][yKeys[0]]) || 0 : 0
      return {
        series: [
          {
            type: "gauge",
            center: ["50%", "60%"],
            radius: "80%",
            startAngle: 200,
            endAngle: -20,
            min: 0,
            max: 100,
            splitNumber: 10,
            itemStyle: { color: getSeriesColor(0) },
            progress: { show: true, width: 20 },
            pointer: { show: false },
            axisLine: { lineStyle: { width: 20, color: [[1, "#1e293b"]] } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            title: { show: false },
            detail: {
              valueAnimation: true,
              fontSize: 24,
              fontWeight: "bold",
              formatter: "{value}",
              color: "#f8fafc",
            },
            data: [{ value: gaugeValue }],
          },
        ],
      }

    default:
      return baseOption
  }
}

function getSeriesColor(index: number, opacity = 1): string {
  const colors = [
    "#3b82f6", // blue
    "#22c55e", // green
    "#f59e0b", // amber
    "#ef4444", // red
    "#8b5cf6", // violet
    "#ec4899", // pink
    "#06b6d4", // cyan
    "#84cc16", // lime
  ]
  const color = colors[index % colors.length]
  if (opacity < 1) {
    // Convert hex to rgba
    const r = parseInt(color.slice(1, 3), 16)
    const g = parseInt(color.slice(3, 5), 16)
    const b = parseInt(color.slice(5, 7), 16)
    return `rgba(${r}, ${g}, ${b}, ${opacity})`
  }
  return color
}

function DataTable({ data: rawData }: { data: Record<string, unknown>[] }) {
  if (!rawData || rawData.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground">
        No data available
      </div>
    )
  }

  const columns = Object.keys(rawData[0])

  return (
    <div className="overflow-auto max-h-[400px] rounded-lg border border-border/40">
      <table className="w-full text-sm">
        <thead className="bg-surface-elevated/50 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground border-b border-border/40">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rawData.map((row, rowIdx) => (
            <tr key={rowIdx} className="hover:bg-muted/30 transition-colors">
              {columns.map((col) => (
                <td key={col} className="px-3 py-2 border-b border-border/20 text-foreground">
                  {formatCellValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "-"
  if (typeof value === "number") {
    // Format numbers with appropriate precision
    return value % 1 === 0 ? value.toString() : value.toFixed(2)
  }
  return String(value)
}

function formatSQL(sql: string): string {
  // Basic SQL formatting - capitalize keywords
  return sql
    .replace(/SELECT/gi, "SELECT")
    .replace(/FROM/gi, "\nFROM")
    .replace(/WHERE/gi, "\nWHERE")
    .replace(/GROUP BY/gi, "\nGROUP BY")
    .replace(/ORDER BY/gi, "\nORDER BY")
    .replace(/LIMIT/gi, "\nLIMIT")
    .replace(/JOIN/gi, "\nJOIN")
    .replace(/LEFT JOIN/gi, "\nLEFT JOIN")
    .replace(/RIGHT JOIN/gi, "\nRIGHT JOIN")
    .replace(/INNER JOIN/gi, "\nINNER JOIN")
    .replace(/ON/gi, "\n  ON")
}

export function ChartRenderer({ data, className, loading, error }: ChartRendererProps) {
  const [activeTab, setActiveTab] = useState<string>(() => {
    // Default to chart if data is not response_table type
    return normalizeChartType(data.type) === "response_table" ? "data" : "chart"
  })

  const chartType = useMemo(() => normalizeChartType(data.type), [data.type])
  const chartOption = useMemo(() => generateEChartsOption(chartType, data.data || []), [chartType, data.data])

  // Determine available tabs
  const hasChart = chartType !== "response_table" && data.data && data.data.length > 0
  const hasSQL = !!data.sql
  const hasData = !!data.data && data.data.length > 0

  // Loading state
  if (loading) {
    return (
      <div className={cn("glass-effect rounded-xl p-4", className)}>
        <div className="flex items-center justify-center h-[300px]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-2 text-muted-foreground">Loading chart...</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className={cn("rounded-xl p-4 border border-destructive/50 bg-destructive/10", className)}>
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <span className="font-medium">Chart Error</span>
        </div>
        <p className="mt-2 text-sm text-destructive/80">{error}</p>
      </div>
    )
  }

  // Empty data state
  if (!data.data || data.data.length === 0) {
    return (
      <div className={cn("glass-effect rounded-xl p-4", className)}>
        <div className="flex items-center justify-center h-[200px] text-muted-foreground">
          <BarChart3 className="h-6 w-6 mr-2 opacity-50" />
          <span>No chart data available</span>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("glass-effect rounded-xl overflow-hidden", className)}>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="w-full justify-start bg-transparent border-b border-border/40 px-2 pt-2 h-auto gap-1">
          {hasChart && (
            <TabsTrigger
              value="chart"
              className="data-[state=active]:bg-muted/50 data-[state=active]:shadow-none rounded-lg px-3 py-1.5 text-sm gap-1.5"
            >
              <BarChart3 className="h-4 w-4" />
              Chart
            </TabsTrigger>
          )}
          {hasSQL && (
            <TabsTrigger
              value="sql"
              className="data-[state=active]:bg-muted/50 data-[state=active]:shadow-none rounded-lg px-3 py-1.5 text-sm gap-1.5"
            >
              <Code className="h-4 w-4" />
              SQL
            </TabsTrigger>
          )}
          {hasData && (
            <TabsTrigger
              value="data"
              className="data-[state=active]:bg-muted/50 data-[state=active]:shadow-none rounded-lg px-3 py-1.5 text-sm gap-1.5"
            >
              <Table className="h-4 w-4" />
              Data
            </TabsTrigger>
          )}
        </TabsList>

        {hasChart && (
          <TabsContent value="chart" className="p-0 m-0">
            <div className="h-[300px] p-2">
              <ReactECharts
                option={chartOption}
                style={{ height: "100%", width: "100%" }}
                opts={{ renderer: "svg" }}
                theme="dark"
              />
            </div>
          </TabsContent>
        )}

        {hasSQL && (
          <TabsContent value="sql" className="p-0 m-0">
            <div className="max-h-[400px] overflow-auto">
              <SyntaxHighlighter
                language="sql"
                style={vscDarkPlus}
                PreTag="div"
                className="!bg-transparent !m-0 text-sm"
              >
                {formatSQL(data.sql || "")}
              </SyntaxHighlighter>
            </div>
          </TabsContent>
        )}

        {hasData && (
          <TabsContent value="data" className="p-2 m-0">
            <DataTable data={data.data || []} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

export default ChartRenderer
