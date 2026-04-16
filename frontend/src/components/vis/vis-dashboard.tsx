import { VisChart } from "./vis-chart"

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

export function VisDashboard({ charts, title }: VisDashboardProps) {
  return (
    <div className="my-2 rounded-xl border border-border bg-surface p-4">
      {title && <h3 className="mb-4 text-lg font-semibold">{title}</h3>}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {charts.map((chart, idx) => (
          <div
            key={idx}
            className="rounded-lg border border-border bg-surface-elevated p-3"
          >
            {chart.err_msg ? (
              <div className="text-sm text-error">{chart.err_msg}</div>
            ) : (
              <VisChart
                data={chart.data}
                type={chart.type}
                title={chart.title || `Chart ${idx + 1}`}
                sql={chart.sql}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
