import { workspaceArchiveUrl } from "../services/workspace-files"

function safeFilename(name: string, fallback: string): string {
  const slug = (name || fallback)
    .split("/")
    .filter(Boolean)
    .at(-1)
    ?.replace(/\.[A-Za-z0-9]+$/, "")
    .replace(/[^\w.\-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
  return slug || fallback
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export function exportTextFile(source: string, filename: string, type = "text/plain;charset=utf-8"): void {
  triggerDownload(new Blob([source], { type }), filename)
}

export function exportHtmlAsMarkdown(source: string, title: string): void {
  exportTextFile(source, `${safeFilename(title, "artifact")}.md`, "text/markdown;charset=utf-8")
}

export function exportHtmlAsStandaloneHtml(source: string, title: string): void {
  exportTextFile(source, `${safeFilename(title, "artifact")}.html`, "text/html;charset=utf-8")
}

export function exportHtmlAsPdf(source: string, title: string): void {
  const win = window.open("", "_blank", "noopener,noreferrer")
  if (!win) return
  win.document.open()
  win.document.write(source)
  win.document.close()
  win.document.title = safeFilename(title, "artifact")
  win.setTimeout(() => {
    win.focus()
    win.print()
  }, 300)
}

export async function exportIframeAsPng(iframe: HTMLIFrameElement | null, title: string): Promise<boolean> {
  const doc = iframe?.contentDocument
  if (!doc?.documentElement) return false
  const width = Math.max(1, iframe?.clientWidth || doc.documentElement.scrollWidth || 1)
  const height = Math.max(1, iframe?.clientHeight || doc.documentElement.scrollHeight || 1)
  const clone = doc.documentElement.cloneNode(true) as HTMLElement
  clone.querySelectorAll("script").forEach((script) => script.remove())
  const html = new XMLSerializer().serializeToString(clone)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><foreignObject width="${width}" height="${height}">${html}</foreignObject></svg>`
  const image = new Image()
  const loaded = new Promise<boolean>((resolve) => {
    image.onload = () => resolve(true)
    image.onerror = () => resolve(false)
  })
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  if (!(await loaded)) return false
  const canvas = document.createElement("canvas")
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(width * dpr)
  canvas.height = Math.floor(height * dpr)
  const ctx = canvas.getContext("2d")
  if (!ctx) return false
  ctx.scale(dpr, dpr)
  ctx.drawImage(image, 0, 0, width, height)
  triggerDownload(await canvasToBlob(canvas), `${safeFilename(title, "artifact")}.png`)
  return true
}

export function workspaceArchiveRoot(filePath: string): string {
  const parts = filePath.split("/").filter(Boolean)
  return parts.length > 1 ? parts[0] : ""
}

export function downloadWorkspaceArchive(workspaceId: string, filePath: string): void {
  const link = document.createElement("a")
  link.href = workspaceArchiveUrl(workspaceId, workspaceArchiveRoot(filePath))
  link.download = ""
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Unable to export PNG"))), "image/png")
  })
}
