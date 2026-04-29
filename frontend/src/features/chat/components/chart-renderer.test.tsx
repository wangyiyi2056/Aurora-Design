import { describe, expect, it } from "vitest"

import { normalizeChartType } from "./chart-renderer"

describe("normalizeChartType", () => {
  it("maps DB-GPT response chart types to local chart types", () => {
    expect(normalizeChartType("response_bar_chart")).toBe("bar")
    expect(normalizeChartType("response_line_chart")).toBe("line")
    expect(normalizeChartType("response_pie_chart")).toBe("pie")
    expect(normalizeChartType("response_scatter_chart")).toBe("scatter")
    expect(normalizeChartType("response_area_chart")).toBe("area")
    expect(normalizeChartType("response_donut_chart")).toBe("pie")
    expect(normalizeChartType("response_bubble_chart")).toBe("scatter")
    expect(normalizeChartType("response_table")).toBe("response_table")
  })

  it("falls back to table for unknown response renderers", () => {
    expect(normalizeChartType("response_heatmap")).toBe("response_table")
    expect(normalizeChartType("response_custom_chart")).toBe("response_table")
  })
})
