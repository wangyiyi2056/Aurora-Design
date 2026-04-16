import { useEffect, useRef } from "react"
import * as echarts from "echarts"

interface VisChartProps {
  data: Record<string, unknown>[]
  type: string
  title?: string
  sql?: string
}

export function VisChart({ data, type, title }: VisChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (type.includes("table") || !chartRef.current || !data.length) return

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)
    }

    const keys = Object.keys(data[0])
    const xKey = keys[0] || "x"
    const yKey = keys[1] || "y"

    const xData = data.map((item) => String(item[xKey]))
    const yData = data.map((item) => {
      const v = item[yKey]
      return typeof v === "number" ? v : Number(v) || 0
    })

    let seriesType = "bar"
    if (type.includes("line")) seriesType = "line"
    else if (type.includes("pie")) seriesType = "pie"
    else if (type.includes("scatter")) seriesType = "scatter"
    else if (type.includes("area")) seriesType = "line"

    let option: echarts.EChartsOption

    if (seriesType === "pie") {
      option = {
        title: { text: title || "Chart", left: "center" },
        tooltip: { trigger: "item" },
        legend: { bottom: "0%" },
        series: [
          {
            type: "pie",
            radius: "50%",
            data: data.map((item) => ({
              name: String(item[xKey]),
              value: Number(item[yKey]) || 0,
            })),
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: "rgba(0, 0, 0, 0.5)",
              },
            },
          },
        ],
      }
    } else {
      option = {
        title: { text: title || "Chart" },
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: xData,
          axisLabel: { rotate: xData.length > 10 ? 45 : 0 },
        },
        yAxis: { type: "value" },
        grid: { left: "3%", right: "4%", bottom: "15%", containLabel: true },
        series: [
          {
            type: seriesType as any,
            data: yData,
            smooth: type.includes("area"),
            areaStyle: type.includes("area") ? {} : undefined,
          },
        ],
        dataZoom: xData.length > 20 ? [{ type: "inside" }, { type: "slider" }] : undefined,
      }
    }

    chartInstance.current.setOption(option, true)

    const handleResize = () => chartInstance.current?.resize()
    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [data, type, title])

  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose()
        chartInstance.current = null
      }
    }
  }, [])

  if (type.includes("table")) {
    if (!data.length) {
      return <div className="text-sm text-text-secondary">No data</div>
    }
    const columns = Object.keys(data[0])
    return (
      <div className="my-2 overflow-auto rounded-lg border border-border bg-surface">
        {title && <div className="px-4 py-2 font-semibold border-b border-border">{title}</div>}
        <table className="w-full text-sm border-collapse">
          <thead className="bg-surface-elevated">
            <tr>
              {columns.map((col) => (
                <th key={col} className="border border-border px-3 py-2 text-left font-semibold whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr key={idx}>
                {columns.map((col) => (
                  <td key={col} className="border border-border px-3 py-2 whitespace-nowrap">
                    {String(row[col] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div
      ref={chartRef}
      style={{ width: "100%", height: 320 }}
      className="my-2 rounded-lg border border-border bg-surface"
    />
  )
}
