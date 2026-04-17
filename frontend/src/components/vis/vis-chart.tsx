import { useEffect, useRef, useState } from "react"
import * as echarts from "echarts"
import { Button, Select, Space, Tooltip, Spin, Alert } from "antd"
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons"

interface VisChartProps {
  data: Record<string, unknown>[]
  type: string
  title?: string
  sql?: string
  describe?: string
}

type ChartType = "bar" | "line" | "pie" | "scatter" | "area" | "table" | "heatmap" | "radar"

const CHART_TYPE_MAP: Record<string, ChartType> = {
  response_bar_chart: "bar",
  response_line_chart: "line",
  response_pie_chart: "pie",
  response_scatter_chart: "scatter",
  response_area_chart: "area",
  response_table: "table",
  response_heatmap_chart: "heatmap",
  response_radar_chart: "radar",
}

const CHART_TYPE_OPTIONS = [
  { value: "bar", label: "柱状图" },
  { value: "line", label: "折线图" },
  { value: "pie", label: "饼图" },
  { value: "scatter", label: "散点图" },
  { value: "area", label: "面积图" },
  { value: "heatmap", label: "热力图" },
  { value: "radar", label: "雷达图" },
  { value: "table", label: "表格" },
]

function inferColumnTypes(data: Record<string, unknown>[]): Record<string, "category" | "number" | "date"> {
  if (!data.length) return {}
  const keys = Object.keys(data[0])
  const types: Record<string, "category" | "number" | "date"> = {}

  for (const key of keys) {
    const values = data.slice(0, 20).map((row) => row[key])
    const numericCount = values.filter((v) => typeof v === "number" || (!isNaN(Number(v)) && v !== "" && v !== null)).length
    const datePattern = values.filter((v) => {
      if (typeof v !== "string") return false
      return /^\d{4}-\d{2}-\d{2}/.test(v) || /^\d{2}\/\d{2}\/\d{4}/.test(v) || /^\d{4}\d{2}\d{2}/.test(v)
    }).length

    if (datePattern > values.length * 0.5) {
      types[key] = "date"
    } else if (numericCount > values.length * 0.5) {
      types[key] = "number"
    } else {
      types[key] = "category"
    }
  }
  return types
}

function getAxisKeys(
  _data: Record<string, unknown>[],
  columnTypes: Record<string, "category" | "number" | "date">
): { xKey: string; yKeys: string[] } {
  const keys = Object.keys(columnTypes)
  const categoryKeys = keys.filter((k) => columnTypes[k] === "category" || columnTypes[k] === "date")
  const numberKeys = keys.filter((k) => columnTypes[k] === "number")

  const xKey = categoryKeys[0] || keys[0]
  const yKeys = numberKeys.length > 0 ? numberKeys : keys.filter((k) => k !== xKey).slice(0, 1)

  return { xKey, yKeys }
}

export function VisChart({ data, type, title, sql, describe }: VisChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSql, setShowSql] = useState(false)

  const initialType = CHART_TYPE_MAP[type] || "bar"
  const [chartType, setChartType] = useState<ChartType>(initialType)

  useEffect(() => {
    setChartType(CHART_TYPE_MAP[type] || "bar")
  }, [type])

  useEffect(() => {
    if (chartType === "table" || !chartRef.current || !data.length) return

    setLoading(true)
    setError(null)

    try {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current, undefined, { renderer: "canvas" })
      }

      const columnTypes = inferColumnTypes(data)
      const { xKey, yKeys } = getAxisKeys(data, columnTypes)
      const xData = data.map((item) => String(item[xKey] ?? ""))

      let option: echarts.EChartsOption

      if (chartType === "pie") {
        const yKey = yKeys[0]
        option = {
          title: { text: title || "Chart", left: "center", top: 10, textStyle: { fontSize: 14 } },
          tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
          legend: { bottom: "5%", left: "center", type: "scroll" },
          series: [
            {
              type: "pie",
              radius: ["40%", "70%"],
              center: ["50%", "45%"],
              data: data.map((item) => ({
                name: String(item[xKey] ?? ""),
                value: Number(item[yKey]) || 0,
              })),
              emphasis: {
                itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0, 0, 0, 0.5)" },
              },
              label: { show: true, formatter: "{b}: {d}%" },
            },
          ],
        }
      } else if (chartType === "scatter") {
        const yKey = yKeys[0]
        option = {
          title: { text: title || "Chart", left: "center", top: 10, textStyle: { fontSize: 14 } },
          tooltip: { trigger: "item", formatter: (params: any) => `${xKey}: ${params.data[0]}<br />${yKey}: ${params.data[1]}` },
          xAxis: { type: "value", name: xKey, nameLocation: "middle", nameGap: 30 },
          yAxis: { type: "value", name: yKey, nameLocation: "middle", nameGap: 40 },
          grid: { left: "12%", right: "10%", bottom: "15%", top: "20%", containLabel: true },
          series: [
            {
              type: "scatter",
              symbolSize: 8,
              data: data.map((item) => [Number(item[xKey]) || 0, Number(item[yKey]) || 0]),
            },
          ],
        }
      } else if (chartType === "heatmap") {
        const yKey = yKeys[0]
        const values = data.map((item) => Number(item[yKey]) || 0)
        const minVal = Math.min(...values)
        const maxVal = Math.max(...values)
        option = {
          title: { text: title || "Heatmap", left: "center", top: 10, textStyle: { fontSize: 14 } },
          tooltip: { position: "top", formatter: (params: any) => `${xKey}: ${params.data[0]}<br />${yKey}: ${params.data[1]}` },
          grid: { height: "50%", top: "15%" },
          xAxis: { type: "category", data: xData, axisLabel: { rotate: xData.length > 10 ? 45 : 0 } },
          yAxis: { type: "category", data: yKeys },
          visualMap: { min: minVal, max: maxVal, calculable: true, orient: "horizontal", left: "center", bottom: "5%", inRange: { color: ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#ffffbf", "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"] } },
          series: [{ type: "heatmap", data: data.map((item, idx) => [String(item[xKey]), yKey, Number(item[yKey]) || 0]), label: { show: true } }],
        }
      } else if (chartType === "radar" && yKeys.length >= 3) {
        const maxValues = yKeys.map((k) => Math.max(...data.map((item) => Number(item[k]) || 0)))
        option = {
          title: { text: title || "Radar", left: "center", top: 10, textStyle: { fontSize: 14 } },
          tooltip: { trigger: "item" },
          radar: {
            indicator: yKeys.map((k, idx) => ({ name: k, max: maxValues[idx] * 1.2 })),
            shape: "polygon",
            splitNumber: 4,
          },
          series: [
            {
              type: "radar",
              data: data.slice(0, 5).map((item, idx) => ({
                name: String(item[xKey] ?? `Item ${idx + 1}`),
                value: yKeys.map((k) => Number(item[k]) || 0),
              })),
            },
          ],
        }
      } else {
        const series: echarts.SeriesOption[] = yKeys.map((yKey, _idx) => ({
          type: chartType === "area" ? "line" : chartType,
          name: yKey,
          data: data.map((item) => Number(item[yKey]) || 0),
          smooth: chartType === "line" || chartType === "area",
          areaStyle: chartType === "area" ? { opacity: 0.3 } : undefined,
          stack: yKeys.length > 1 && chartType === "area" ? "total" : undefined,
        }))

        option = {
          title: { text: title || "Chart", left: "center", top: 10, textStyle: { fontSize: 14 } },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
          },
          legend: yKeys.length > 1 ? { bottom: "5%", left: "center", type: "scroll" } : undefined,
          xAxis: {
            type: "category",
            data: xData,
            axisLabel: { rotate: xData.length > 10 ? 45 : 0, interval: Math.floor(xData.length / 15), overflow: "truncate", width: 80 },
          },
          yAxis: { type: "value" },
          grid: { left: "5%", right: "5%", bottom: yKeys.length > 1 ? "15%" : "10%", top: "15%", containLabel: true },
          series,
          dataZoom: xData.length > 30 ? [{ type: "inside", start: 0, end: 100 }, { type: "slider", bottom: 0, start: 0, end: 100 }] : undefined,
        }
      }

      chartInstance.current.setOption(option, true)
      setLoading(false)
    } catch (err) {
      setError(`图表渲染失败: ${err}`)
      setLoading(false)
    }

    const handleResize = () => {
      chartInstance.current?.resize()
    }
    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [data, chartType, title])

  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose()
        chartInstance.current = null
      }
    }
  }, [])

  const handleDownload = () => {
    if (!chartInstance.current) return
    const url = chartInstance.current.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" })
    const link = document.createElement("a")
    link.download = `${title || "chart"}.png`
    link.href = url
    link.click()
  }

  const handleRefresh = () => {
    if (chartInstance.current && chartRef.current) {
      chartInstance.current.resize()
    }
  }

  if (!data || data.length === 0) {
    return (
      <div className="my-2 rounded-lg border border-border bg-surface p-4">
        <Alert type="warning" message="无数据" description="该图表没有数据可供展示" showIcon />
      </div>
    )
  }

  if (chartType === "table") {
    const columns = Object.keys(data[0])
    return (
      <div className="my-2 overflow-auto rounded-lg border border-border bg-surface max-h-[400px]">
        {title && <div className="px-4 py-2 font-semibold border-b border-border bg-surface-elevated">{title}</div>}
        {describe && <div className="px-4 py-1 text-sm text-text-secondary bg-surface-elevated">{describe}</div>}
        <table className="w-full text-sm border-collapse">
          <thead className="bg-surface-elevated sticky top-0">
            <tr>
              {columns.map((col) => (
                <th key={col} className="border border-border px-3 py-2 text-left font-semibold whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 100).map((row, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? "bg-surface" : "bg-surface-elevated"}>
                {columns.map((col) => (
                  <td key={col} className="border border-border px-3 py-2 whitespace-nowrap">
                    {String(row[col] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {data.length > 100 && (
          <div className="text-sm text-text-secondary text-center py-2 bg-surface-elevated">
            显示前 100 条，共 {data.length} 条数据
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="my-2 rounded-lg border border-border bg-surface">
      <div className="flex justify-between items-center px-4 py-2 border-b border-border flex-wrap gap-2">
        <Space wrap>
          <span className="text-sm text-text-secondary">图表类型:</span>
          <Select
            value={chartType}
            onChange={setChartType}
            options={CHART_TYPE_OPTIONS}
            size="small"
            className="w-28"
          />
          {sql && (
            <Button type="link" size="small" onClick={() => setShowSql(!showSql)}>
              {showSql ? "隐藏 SQL" : "显示 SQL"}
            </Button>
          )}
        </Space>
        <Space>
          <Tooltip title="刷新图表">
            <Button type="text" size="small" icon={<ReloadOutlined />} onClick={handleRefresh} />
          </Tooltip>
          <Tooltip title="下载图表">
            <Button type="text" size="small" icon={<DownloadOutlined />} onClick={handleDownload} />
          </Tooltip>
        </Space>
      </div>
      {showSql && sql && (
        <div className="px-4 py-2 bg-surface-elevated text-xs text-text-secondary overflow-auto max-h-[100px]">
          <pre className="whitespace-pre-wrap">{sql}</pre>
        </div>
      )}
      {describe && !showSql && (
        <div className="px-4 py-1 text-sm text-text-secondary">{describe}</div>
      )}
      {loading && (
        <div className="flex justify-center items-center h-[320px]">
          <Spin tip="加载中..." />
        </div>
      )}
      {error && (
        <div className="px-4 py-2">
          <Alert type="error" message="渲染错误" description={error} showIcon />
        </div>
      )}
      <div ref={chartRef} style={{ width: "100%", height: 320, minHeight: 200 }} className={loading || error ? "hidden" : ""} />
    </div>
  )
}