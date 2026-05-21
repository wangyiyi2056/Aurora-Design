import { describe, expect, it } from "vitest"

import { artifactFromStreamEvent, safeFileStem } from "./generated-artifacts"

describe("generated workspace artifacts", () => {
  it("extracts html step chunks as generated files", () => {
    const artifact = artifactFromStreamEvent({
      type: "step.chunk",
      id: "render",
      output_type: "html",
      content: { title: "Report/May", html: "<html><body>ok</body></html>" },
    })

    expect(artifact).toMatchObject({
      name: "generated/Report-May.html",
      content: "<html><body>ok</body></html>",
      shouldOpen: true,
    })
  })

  it("sanitizes unsafe file stems", () => {
    expect(safeFileStem("../bad:name?.html")).toBe("bad-name")
  })
})
