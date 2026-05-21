import { describe, expect, it } from "vitest"

import { workspaceArchiveUrl, workspaceRawUrl } from "./workspace-files"

describe("workspaceRawUrl", () => {
  it("encodes workspace id and path segments while preserving path separators", () => {
    expect(workspaceRawUrl("session 1", "reports/首页 demo.html")).toBe(
      "/api/v1/workspaces/session%201/raw/reports/%E9%A6%96%E9%A1%B5%20demo.html"
    )
  })

  it("builds archive URLs for a whole workspace or subdirectory", () => {
    expect(workspaceArchiveUrl("session 1")).toBe("/api/v1/workspaces/session%201/archive")
    expect(workspaceArchiveUrl("session 1", "generated/site")).toBe(
      "/api/v1/workspaces/session%201/archive?root=generated%2Fsite"
    )
  })
})
