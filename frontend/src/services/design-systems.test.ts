import { describe, expect, it, vi } from "vitest"
import { apiClient } from "@/lib/api-client"
import {
  createDesignSystem,
  deleteDesignSystem,
  designSystemPreviewUrl,
  getDesignSystem,
  listDesignSystems,
  updateDesignSystem,
} from "./design-systems"

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe("design system service", () => {
  it("uses the design-systems API paths", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { designSystems: [{ id: "vercel" }] } })
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { id: "vercel", body: "# Vercel" } })
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { id: "aurora" } })
    vi.mocked(apiClient.patch).mockResolvedValueOnce({ data: { id: "aurora", status: "published" } })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: undefined })

    await expect(listDesignSystems()).resolves.toEqual([{ id: "vercel" }])
    await expect(getDesignSystem("vercel")).resolves.toEqual({ id: "vercel", body: "# Vercel" })
    await createDesignSystem({ title: "Aurora" })
    await updateDesignSystem("aurora", { status: "published" })
    await deleteDesignSystem("aurora")

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/v1/design-systems")
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/v1/design-systems/vercel")
    expect(apiClient.post).toHaveBeenCalledWith("/v1/design-systems", { title: "Aurora" })
    expect(apiClient.patch).toHaveBeenCalledWith("/v1/design-systems/aurora", { status: "published" })
    expect(apiClient.delete).toHaveBeenCalledWith("/v1/design-systems/aurora")
    expect(designSystemPreviewUrl("vercel")).toBe("/api/v1/design-systems/vercel/preview")
  })
})
