import { describe, expect, it } from "vitest"

import {
  ReactAgentSSEState,
  buildArtifactsFromExecution,
  getPreferredPanelView,
  parseReactAgentSSELine,
} from "./react-agent-workspace"

describe("ReactAgentSSEState", () => {
  it("parses DB-GPT style events into execution state", () => {
    const state = new ReactAgentSSEState()
    const lines = [
      'data: {"type":"step.start","id":"step-1","step":1,"title":"执行 SQL","detail":"DuckDB"}',
      'data: {"type":"step.meta","id":"step-1","thought":"准备执行","action":"execute_sql","action_input":{"sql":"select 1"}}',
      'data: {"type":"step.chunk","id":"step-1","output_type":"code","content":"select 1"}',
      'data: {"type":"step.done","id":"step-1","status":"done"}',
      'data: {"type":"final","content":"分析完成"}',
      'data: {"type":"done"}',
    ]

    for (const line of lines) {
      const event = parseReactAgentSSELine(line)
      if (event) state.processEvent(event)
    }

    const snapshot = state.getSnapshot()
    expect(snapshot.steps[0]).toMatchObject({
      id: "step-1",
      title: "执行 SQL",
      status: "completed",
      action: "execute_sql",
    })
    expect(snapshot.outputs["step-1"][0]).toEqual({
      output_type: "code",
      content: "select 1",
    })
    expect(snapshot.summary).toBe("分析完成")
    expect(snapshot.isDone).toBe(true)
  })
})

describe("buildArtifactsFromExecution", () => {
  it("creates Report.html artifact from html output and prefers report panel", () => {
    const artifacts = buildArtifactsFromExecution({
      steps: [{ id: "step-render", title: "渲染报告", status: "completed", type: "html" }],
      outputs: {
        "step-render": [
          {
            output_type: "html",
            content: { title: "Report", html: "<html><body>ok</body></html>" },
          },
        ],
      },
      summary: "done",
    })

    expect(artifacts).toHaveLength(2)
    expect(artifacts[0]).toMatchObject({
      type: "html",
      name: "Report.html",
      content: "<html><body>ok</body></html>",
    })
    expect(getPreferredPanelView(artifacts)).toBe("html-preview")
  })
})
