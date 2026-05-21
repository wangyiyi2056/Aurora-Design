import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { describe, expect, it } from "vitest"

import { FileWorkspace } from "./file-workspace"
import type { WorkspaceFile } from "../types"

describe("FileWorkspace", () => {
  it("opens an html file from the file browser into a preview tab", () => {
    const files: WorkspaceFile[] = [
      {
        name: "reports/index.html",
        path: "reports/index.html",
        type: "file",
        size: 120,
        mtime: 1,
        kind: "html",
        mime: "text/html",
      },
    ]

    render(<FileWorkspace workspaceId="session-1" files={files} />)

    fireEvent.click(screen.getByRole("button", { name: /reports\/index.html/ }))

    expect(screen.getByRole("tab", { name: /index.html/ })).toBeVisible()
    expect(screen.getByTitle("reports/index.html")).toBeVisible()
    expect(screen.queryByText("1 items")).not.toBeInTheDocument()
  })
})
