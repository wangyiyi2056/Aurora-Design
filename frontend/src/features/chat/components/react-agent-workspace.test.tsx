import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ReactAgentWorkspace } from "./react-agent-workspace"
import type {
  ReactAgentArtifact,
  ReactAgentSnapshot,
} from "@/features/chat/utils/react-agent-workspace"

describe("ReactAgentWorkspace", () => {
  it("renders DB-GPT style split workspace with Report.html preview", () => {
    const snapshot: ReactAgentSnapshot = {
      steps: [
        {
          id: "step-render-report",
          step: 5,
          title: "生成 HTML 报告",
          detail: "html_interpreter",
          status: "completed",
          action: "html_interpreter",
          type: "html",
        },
      ],
      outputs: {
        "step-render-report": [
          {
            output_type: "html",
            content: { title: "Report", html: "<h1>分析报告</h1>" },
          },
        ],
      },
      activeStepId: "step-render-report",
      summary: "分析完成",
      isDone: true,
    }
    const artifacts: ReactAgentArtifact[] = [
      {
        id: "report",
        type: "html",
        name: "Report.html",
        content: "<h1>分析报告</h1>",
        createdAt: Date.now(),
      },
    ]

    render(
      <ReactAgentWorkspace
        userQuestion="按类别统计销售额"
        snapshot={snapshot}
        artifacts={artifacts}
        panelView="html-preview"
        onPanelViewChange={vi.fn()}
        loading={false}
        inputArea={<div>输入框</div>}
      />
    )

    expect(screen.getByText("DB-GPT 的电脑")).toBeTruthy()
    expect(screen.getAllByText("执行步骤").length).toBeGreaterThan(0)
    expect(screen.getByText("Report.html")).toBeTruthy()
    expect(screen.getByTitle("Report.html")).toBeTruthy()
  })
})
