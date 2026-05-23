import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { FileWorkspace } from "./file-workspace"
import type { WorkspaceFile } from "../types"
import { deleteWorkspaceFile } from "../services/workspace-files"

vi.mock("../services/workspace-files", async () => {
  const actual = await vi.importActual<typeof import("../services/workspace-files")>("../services/workspace-files")
  return {
    ...actual,
    deleteWorkspaceFile: vi.fn().mockResolvedValue(true),
  }
})

describe("FileWorkspace", () => {
  beforeEach(() => {
    vi.mocked(deleteWorkspaceFile).mockClear()
    vi.mocked(deleteWorkspaceFile).mockResolvedValue(true)
  })

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

  it("groups files by type and deletes selected files together", async () => {
    const onRefreshFiles = vi.fn()
    const files: WorkspaceFile[] = [
      {
        name: "uploads/logo.png",
        path: "uploads/logo.png",
        type: "file",
        size: 120,
        mtime: 3,
        kind: "image",
        mime: "image/png",
      },
      {
        name: "data/sales.csv",
        path: "data/sales.csv",
        type: "file",
        size: 240,
        mtime: 2,
        kind: "spreadsheet",
        mime: "text/csv",
      },
      {
        name: "generated/report.html",
        path: "generated/report.html",
        type: "file",
        size: 360,
        mtime: 1,
        kind: "html",
        mime: "text/html",
      },
    ]

    render(<FileWorkspace workspaceId="session-1" files={files} onRefreshFiles={onRefreshFiles} />)

    expect(screen.getByText("Images")).toBeVisible()
    expect(screen.getByText("Data")).toBeVisible()
    expect(screen.getByText("Code")).toBeVisible()

    fireEvent.click(screen.getByRole("checkbox", { name: "Select uploads/logo.png" }))
    fireEvent.click(screen.getByRole("checkbox", { name: "Select data/sales.csv" }))
    fireEvent.click(screen.getByRole("button", { name: "Delete selected files" }))

    await waitFor(() => {
      expect(deleteWorkspaceFile).toHaveBeenCalledWith("session-1", "uploads/logo.png")
      expect(deleteWorkspaceFile).toHaveBeenCalledWith("session-1", "data/sales.csv")
    })
    expect(onRefreshFiles).toHaveBeenCalled()
  })
})
