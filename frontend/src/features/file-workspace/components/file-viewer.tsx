import { useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import ReactMarkdown from "react-markdown"
import {
  Archive,
  Check,
  Copy,
  Download,
  ExternalLink,
  FileDown,
  FileQuestion,
  Image as ImageIcon,
  Printer,
  RefreshCw,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  exportHtmlAsMarkdown,
  exportHtmlAsPdf,
  exportHtmlAsStandaloneHtml,
  exportIframeAsPng,
  downloadWorkspaceArchive,
} from "../runtime/workspace-exports"
import {
  fetchWorkspaceFileText,
  workspaceRawUrl,
  fetchWorkspaceFilePreviewInfo,
  workspacePreviewPdfUrl,
} from "../services/workspace-files"
import type { WorkspaceFile } from "../types"
import jsPreviewExcel from "@js-preview/excel"
import "@js-preview/excel/lib/index.css"
import mammoth from "mammoth"
import Papa from "papaparse"
import { init as initPptxPreview } from "pptx-preview"

interface FileViewerProps {
  workspaceId: string
  file: WorkspaceFile
}

type Viewport = "desktop" | "tablet" | "mobile"
type SourceMode = "preview" | "source"

const viewportClass: Record<Viewport, string> = {
  desktop: "w-full",
  tablet: "w-[820px] max-w-full",
  mobile: "w-[390px] max-w-full",
}

// ─── DOCX iframe styles ───────────────────────────────────────────────────────
// Injected into iframe srcDoc — fully isolated from Tailwind CSS reset.
const DOCX_IFRAME_STYLE = `
  body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px; line-height: 1.7; color: #1a1a1a;
    padding: 1.5rem 2.5rem; margin: 0; max-width: 860px;
  }
  p { margin-bottom: 0.6rem; }
  h1 { font-size: 1.6rem; font-weight: 700; margin: 1.2rem 0 0.6rem; }
  h2 { font-size: 1.3rem; font-weight: 600; margin: 1rem 0 0.5rem; }
  h3 { font-size: 1.1rem; font-weight: 600; margin: 0.9rem 0 0.4rem; }
  h4,h5,h6 { font-weight: 600; margin: 0.8rem 0 0.4rem; }
  ul,ol { padding-left: 1.5rem; margin-bottom: 0.6rem; }
  li { margin-bottom: 0.25rem; }
  strong,b { font-weight: 600; }
  em,i { font-style: italic; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
  td,th { border: 1px solid #ddd; padding: 6px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  img { max-width: 100%; height: auto; }
  a { color: #2563eb; text-decoration: underline; }
  blockquote { border-left: 3px solid #ddd; margin: 0.75rem 0; padding: 0.25rem 1rem; color: #555; }
  code { background: #f1f1f1; border-radius: 3px; padding: 0.1em 0.35em; font-size: 0.9em; font-family: monospace; }
`

// ─── Router ───────────────────────────────────────────────────────────────────
export function FileViewer({ workspaceId, file }: FileViewerProps) {
  if (file.kind === "html") return <HtmlViewer workspaceId={workspaceId} file={file} />
  if (isSvg(file)) return <SvgViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "image" || file.kind === "sketch") return <ImageViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "video" || file.kind === "audio") return <MediaViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "markdown") return <MarkdownViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "text" || file.kind === "code" || file.kind === "json") {
    return <TextViewer workspaceId={workspaceId} file={file} />
  }
  if (file.kind === "pdf") return <PdfViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "spreadsheet") {
    if (file.name.toLowerCase().endsWith(".csv")) return <CsvViewer workspaceId={workspaceId} file={file} />
    return <ExcelViewer workspaceId={workspaceId} file={file} />
  }
  if (file.kind === "document") return <DocxViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "presentation") return <PptxViewer workspaceId={workspaceId} file={file} />
  return <BinaryViewer workspaceId={workspaceId} file={file} />
}

// ─── HTML Viewer ──────────────────────────────────────────────────────────────
function HtmlViewer({ workspaceId, file }: FileViewerProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [viewport, setViewport] = useState<Viewport>("desktop")
  const [mode, setMode] = useState<SourceMode>("preview")
  const [zoom, setZoom] = useState(100)
  const [source, setSource] = useState<string | null>(null)
  const [exportingPng, setExportingPng] = useState(false)
  const src = `${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}&r=${reloadKey}`

  useEffect(() => {
    let cancelled = false
    fetchWorkspaceFileText(workspaceId, file.name, {
      cacheBustKey: `${file.mtime}-${reloadKey}`,
      cache: "no-store",
    }).then((value) => { if (!cancelled) setSource(value ?? "") })
    return () => { cancelled = true }
  }, [file.mtime, file.name, reloadKey, workspaceId])

  const previewScale = zoom / 100

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <ViewerToolbar
        left={
          <>
            <Segmented value={mode} options={["preview", "source"]} onChange={(v) => setMode(v as SourceMode)} />
            {mode === "preview" && (
              <>
                <span className="h-5 w-px bg-border" />
                <Segmented value={viewport} options={["desktop", "tablet", "mobile"]} onChange={(v) => setViewport(v as Viewport)} />
                <span className="h-5 w-px bg-border" />
                <Segmented
                  value={String(zoom)}
                  options={["50", "75", "100", "125", "150"]}
                  labels={{ "50": "50%", "75": "75%", "100": "100%", "125": "125%", "150": "150%" }}
                  onChange={(v) => setZoom(Number(v))}
                />
              </>
            )}
          </>
        }
        right={
          <>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Refresh preview" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export PDF" disabled={!source} onClick={() => source && exportHtmlAsPdf(source, file.name)}>
              <Printer className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export PNG" disabled={mode !== "preview" || exportingPng}
              onClick={async () => { setExportingPng(true); try { await exportIframeAsPng(iframeRef.current, file.name) } finally { setExportingPng(false) } }}>
              <ImageIcon className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export Markdown" disabled={!source} onClick={() => source && exportHtmlAsMarkdown(source, file.name)}>
              <FileDown className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export ZIP" onClick={() => downloadWorkspaceArchive(workspaceId, file.name)}>
              <Archive className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export HTML" disabled={!source} onClick={() => source && exportHtmlAsStandaloneHtml(source, file.name)}>
              <Download className="h-4 w-4" />
            </Button>
            <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Open in new tab">
              <a href={src} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" /></a>
            </Button>
          </>
        }
      />
      <div className={cn("min-h-0 flex-1 overflow-auto bg-muted/30", mode === "preview" ? "p-4 flex items-center justify-center" : "")}>
        {mode === "source" ? (
          <CodeWithLines text={source ?? ""} />
        ) : (
          <div className="mx-auto" style={{ transform: `scale(${previewScale})`, transformOrigin: "center center", width: `${100 / previewScale}%`, height: `${100 / previewScale}%`, minHeight: `${520 / previewScale}px` }}>
            <iframe ref={iframeRef} key={src} title={file.name} src={src}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
              className={cn("mx-auto h-full rounded-md border bg-white", viewportClass[viewport])} />
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Image Viewer ─────────────────────────────────────────────────────────────
function ImageViewer({ workspaceId, file }: FileViewerProps) {
  const src = `${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto bg-muted/30 p-5">
        <img src={src} alt={file.name} className="max-h-full max-w-full rounded-md object-contain" />
      </div>
    </div>
  )
}

// ─── SVG Viewer ───────────────────────────────────────────────────────────────
function SvgViewer({ workspaceId, file }: FileViewerProps) {
  const [mode, setMode] = useState<SourceMode>("preview")
  const [text, setText] = useWorkspaceText(workspaceId, file)
  const src = `${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<Segmented value={mode} options={["preview", "source"]} onChange={(v) => setMode(v as SourceMode)} />}
        right={<FileActions workspaceId={workspaceId} file={file} extra={<ReloadButton onClick={() => setText(null)} />} />}
      />
      <div className={cn("min-h-0 flex-1 overflow-auto bg-muted/30 p-5", mode === "preview" && "flex items-center justify-center")}>
        {mode === "preview" ? <img src={src} alt={file.name} className="max-h-full max-w-full rounded-md object-contain" /> : <CodeWithLines text={text ?? ""} />}
      </div>
    </div>
  )
}

// ─── Media Viewer ─────────────────────────────────────────────────────────────
function MediaViewer({ workspaceId, file }: FileViewerProps) {
  const src = workspaceRawUrl(workspaceId, file.name)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="flex min-h-0 flex-1 items-center justify-center bg-muted/30 p-5">
        {file.kind === "video"
          ? <video src={src} controls playsInline preload="metadata" className="max-h-full max-w-full rounded-md" />
          : <audio src={src} controls preload="metadata" className="w-full max-w-xl" />}
      </div>
    </div>
  )
}

// ─── Markdown Viewer ──────────────────────────────────────────────────────────
function MarkdownViewer({ workspaceId, file }: FileViewerProps) {
  const [mode, setMode] = useState<SourceMode>("preview")
  const [copied, copy] = useCopyState()
  const [text, setText] = useWorkspaceText(workspaceId, file)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<Segmented value={mode} options={["preview", "source"]} onChange={(v) => setMode(v as SourceMode)} />}
        right={<><ReloadButton onClick={() => setText(null)} /><CopyButton copied={copied} onClick={() => copy(text ?? "")} /><FileActions workspaceId={workspaceId} file={file} /></>}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        {mode === "source" ? (
          <CodeWithLines text={text ?? ""} />
        ) : (
          <article className="prose prose-sm max-w-none p-6 text-foreground prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground">
            <ReactMarkdown>{text ?? ""}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  )
}

// ─── Text / Code / JSON Viewer ────────────────────────────────────────────────
function TextViewer({ workspaceId, file }: FileViewerProps) {
  const [copied, copy] = useCopyState()
  const [text, setText] = useWorkspaceText(workspaceId, file)
  const displayText = useMemo(() => (file.kind === "json" ? formatJsonSafely(text ?? "") : text ?? ""), [file.kind, text])
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>}
        right={<><ReloadButton onClick={() => setText(null)} /><CopyButton copied={copied} onClick={() => copy(displayText)} /><FileActions workspaceId={workspaceId} file={file} /></>}
      />
      <div className="min-h-0 flex-1 overflow-auto"><CodeWithLines text={displayText} /></div>
    </div>
  )
}

// ─── PDF Viewer ───────────────────────────────────────────────────────────────
function PdfViewer({ workspaceId, file }: FileViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">PDF · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <iframe title={file.name} src={`${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`} className="min-h-0 flex-1 border-0 bg-white" />
    </div>
  )
}

// ─── Excel Viewer ─────────────────────────────────────────────────────────────
function ExcelViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let previewer: any = null

    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetch(workspaceRawUrl(workspaceId, file.name))
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const buf = await res.arrayBuffer()
        if (cancelled || !containerRef.current) return
        previewer = jsPreviewExcel.init(containerRef.current)
        previewer
          .preview(buf)
          .then(() => { if (!cancelled) setLoading(false) })
          .catch((e: unknown) => {
            previewer?.destroy()
            if (!cancelled) { setError(String(e)); setLoading(false) }
          })
      } catch (e) {
        if (!cancelled) { setError(String(e)); setLoading(false) }
      }
    }

    load()
    return () => { cancelled = true; previewer?.destroy() }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">Excel · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 320 }}>
        <div ref={containerRef} style={{ minHeight: 320 }} />
        <ViewerOverlay loading={loading} error={error} />
      </div>
    </div>
  )
}

// ─── CSV Viewer ───────────────────────────────────────────────────────────────
// Blob → FileReader for reliable cross-browser encoding (ragflow pattern)
function CsvViewer({ workspaceId, file }: FileViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        setLoading(true); setError(null)
        const res = await fetch(workspaceRawUrl(workspaceId, file.name))
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        const text = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.readAsText(blob)
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(reader.error)
        })
        if (cancelled) return
        const result = Papa.parse<string[]>(text, { header: false, skipEmptyLines: false })
        const all = result.data as string[][]
        if (all.length > 0) { setHeaders(all[0]); setRows(all.slice(1)) }
      } catch (e) {
        if (!cancelled) setError(String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">CSV · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 320 }}>
        <ViewerOverlay loading={loading} error={error} />
        {!loading && !error && headers.length > 0 && (
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm">
              <tr>{headers.map((h, i) => <th key={i} className="px-4 py-2 text-left font-medium whitespace-nowrap">{h || `Col ${i + 1}`}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row, ri) => (
                <tr key={ri} className="hover:bg-muted/30">
                  {row.map((cell, ci) => <td key={ci} className="px-4 py-2 whitespace-nowrap text-muted-foreground">{cell || "–"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && !error && headers.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">File is empty</div>
        )}
      </div>
    </div>
  )
}

// ─── DOCX Viewer ──────────────────────────────────────────────────────────────
// Step 1: Try LibreOffice PDF via backend.
// Step 2: Fetch as blob → probe ZIP magic (0x50 0x4B) → mammoth → iframe srcDoc.
// iframe srcDoc isolates mammoth HTML from Tailwind CSS resets entirely.
function DocxViewer({ workspaceId, file }: FileViewerProps) {
  const [status, setStatus] = useState<"loading" | "pdf" | "html" | "unsupported" | "error">("loading")
  const [htmlContent, setHtmlContent] = useState("")
  const [pdfSrc, setPdfSrc] = useState("")
  const [errorMsg, setErrorMsg] = useState("")

  useEffect(() => {
    let cancelled = false
    setStatus("loading")
    setHtmlContent("")
    setPdfSrc("")
    setErrorMsg("")

    const load = async () => {
      try {
        // Step 1 — LibreOffice backend conversion
        const info = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (info?.previewAvailable) {
          if (!cancelled) {
            setPdfSrc(`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`)
            setStatus("pdf")
          }
          return
        }

        // Step 2 — client-side mammoth fallback
        const rawUrl = workspaceRawUrl(workspaceId, file.name)
        const res = await fetch(rawUrl)
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${rawUrl}`)
        const blob = await res.blob()
        if (cancelled) return

        // Probe ZIP magic bytes — valid .docx files are ZIP archives (PK header)
        const hdrBuf = await blob.slice(0, 4).arrayBuffer()
        const hdr = new Uint8Array(hdrBuf)
        const isZip = hdr[0] === 0x50 && hdr[1] === 0x4b

        if (!isZip) {
          if (!cancelled) setStatus("unsupported")
          return
        }

        const buf = await blob.arrayBuffer()
        const result = await mammoth.convertToHtml({ arrayBuffer: buf }, { includeDefaultStyleMap: true })
        if (!cancelled) { setHtmlContent(result.value); setStatus("html") }
      } catch (e) {
        console.error("[DocxViewer]", e)
        if (!cancelled) { setErrorMsg(String(e)); setStatus("error") }
      }
    }

    load()
    return () => { cancelled = true }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">Document · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <div className="relative flex-1" style={{ minHeight: 400 }}>
        {status === "loading" && <ViewerOverlay loading error={null} />}
        {status === "error" && (
          <div className="flex h-full items-center justify-center p-8 text-sm text-destructive">
            Failed to load: {errorMsg}
          </div>
        )}
        {status === "unsupported" && (
          <div className="flex h-full items-center justify-center p-8">
            <div className="max-w-sm rounded-xl border border-dashed p-6 text-center">
              <p className="font-semibold">Preview not available</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Only modern <code>.docx</code> files are supported.<br />
                This file uses the legacy <code>.doc</code> format.
              </p>
            </div>
          </div>
        )}
        {status === "pdf" && (
          <iframe title={file.name} src={pdfSrc} className="absolute inset-0 h-full w-full border-0" />
        )}
        {status === "html" && (
          <iframe
            title={file.name}
            srcDoc={`<!doctype html><html><head><meta charset="utf-8"><style>${DOCX_IFRAME_STYLE}</style></head><body>${htmlContent}</body></html>`}
            className="absolute inset-0 h-full w-full border-0 bg-white"
          />
        )}
      </div>
    </div>
  )
}

// ─── PPTX Viewer ──────────────────────────────────────────────────────────────
// containerRef = outer wrapper (fixed minHeight → reliable clientWidth/Height)
// wrapperRef   = render target passed to pptx-preview library
function PptxViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<"loading" | "pdf" | "rendered" | "error">("loading")
  const [pdfSrc, setPdfSrc] = useState("")
  const [errorMsg, setErrorMsg] = useState("")

  useEffect(() => {
    let cancelled = false
    let viewer: any = null
    setStatus("loading")
    setPdfSrc("")
    setErrorMsg("")

    const load = async () => {
      try {
        // Step 1 — LibreOffice backend conversion
        const info = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (info?.previewAvailable) {
          if (!cancelled) {
            setPdfSrc(`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`)
            setStatus("pdf")
          }
          return
        }

        // Step 2 — pptx-preview library fallback
        const rawUrl = workspaceRawUrl(workspaceId, file.name)
        const res = await fetch(rawUrl)
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${rawUrl}`)
        const buf = await res.arrayBuffer()

        if (cancelled) return

        // containerRef has minHeight:600 so dimensions are available immediately
        const el = containerRef.current
        const wrap = wrapperRef.current
        if (!el || !wrap) throw new Error("Container not mounted")

        const width = Math.max(el.clientWidth - 50, 300)
        const height = Math.max(el.clientHeight - 50, 300)

        viewer = initPptxPreview(wrap, { width, height })
        await viewer.preview(buf)
        if (!cancelled) setStatus("rendered")
      } catch (e) {
        console.error("[PptxViewer]", e)
        if (!cancelled) { setErrorMsg(String(e)); setStatus("error") }
      }
    }

    load()
    return () => { cancelled = true; viewer?.destroy() }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">Presentation · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      {/* containerRef: fixed minHeight gives reliable dimensions for pptx-preview */}
      <div ref={containerRef} className="relative flex-1 overflow-auto" style={{ minHeight: 600 }}>
        {status === "loading" && <ViewerOverlay loading error={null} />}
        {status === "error" && (
          <div className="flex h-full min-h-[600px] items-center justify-center p-8">
            <div className="max-w-sm rounded-xl border border-dashed p-6 text-center">
              <p className="font-semibold">Preview failed</p>
              <p className="mt-2 text-sm text-muted-foreground">{errorMsg}</p>
            </div>
          </div>
        )}
        {status === "pdf" && (
          <iframe title={file.name} src={pdfSrc} className="absolute inset-0 h-full w-full border-0" />
        )}
        {/* wrapperRef: render target for pptx-preview; only visible when rendered */}
        <div className={cn("overflow-auto p-2", status !== "rendered" && "hidden")}>
          <div className="flex flex-col gap-4">
            <div ref={wrapperRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Binary Viewer ────────────────────────────────────────────────────────────
function BinaryViewer({ workspaceId, file }: FileViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">binary · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md rounded-lg border bg-card p-5 text-center">
          <FileQuestion className="mx-auto h-8 w-8 text-muted-foreground" />
          <h3 className="mt-3 text-sm font-semibold">{file.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">Preview is unavailable for this file type. Size: {humanSize(file.size)}</p>
        </div>
      </div>
    </div>
  )
}

// ─── Shared UI ────────────────────────────────────────────────────────────────

function ViewerToolbar({ left, right }: { left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-11 shrink-0 items-center justify-between gap-3 border-b px-3 py-1">
      <div className="flex min-w-0 flex-wrap items-center gap-1">{left}</div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">{right}</div>
    </div>
  )
}

/** Requires parent `position: relative`. */
function ViewerOverlay({ loading, error }: { loading: boolean; error: string | null }) {
  if (!loading && !error) return null
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70 backdrop-blur-sm">
      {loading && <span className="animate-pulse text-sm text-muted-foreground">Loading preview…</span>}
      {!loading && error && <span className="text-sm text-destructive">{error}</span>}
    </div>
  )
}

function FileActions({ workspaceId, file, extra }: { workspaceId: string; file: WorkspaceFile; extra?: ReactNode }) {
  return (
    <>
      {extra}
      <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Download">
        <a href={workspaceRawUrl(workspaceId, file.name)} download><Download className="h-4 w-4" /></a>
      </Button>
      <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Open in new tab">
        <a href={workspaceRawUrl(workspaceId, file.name)} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" /></a>
      </Button>
    </>
  )
}

function Segmented({ value, options, labels, onChange }: { value: string; options: string[]; labels?: Record<string, string>; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-1 rounded-md border bg-muted/50 p-0.5">
      {options.map((item) => (
        <button key={item} type="button" aria-pressed={value === item}
          className={cn("h-7 rounded-[5px] px-2 text-xs font-medium capitalize transition-colors", value === item ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-background hover:text-foreground")}
          onClick={() => onChange(item)}>
          {labels?.[item] ?? item}
        </button>
      ))}
    </div>
  )
}

function ReloadButton({ onClick }: { onClick: () => void }) {
  return <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Reload" onClick={onClick}><RefreshCw className="h-4 w-4" /></Button>
}

function CopyButton({ copied, onClick }: { copied: boolean; onClick: () => void }) {
  return <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Copy" onClick={onClick}>{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</Button>
}

function CodeWithLines({ text }: { text: string }) {
  return (
    <pre className="h-full overflow-auto p-4 text-xs leading-6">
      {text.split("\n").map((line, i) => (
        <div key={i} className="grid grid-cols-[3rem_1fr] gap-3">
          <span className="select-none text-right text-muted-foreground">{i + 1}</span>
          <span className="whitespace-pre-wrap break-words">{line || " "}</span>
        </div>
      ))}
    </pre>
  )
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

function useWorkspaceText(workspaceId: string, file: WorkspaceFile): [string | null, (v: string | null) => void] {
  const [text, setText] = useState<string | null>(null)
  useEffect(() => {
    if (text !== null) return
    let cancelled = false
    fetchWorkspaceFileText(workspaceId, file.name, { cacheBustKey: file.mtime, cache: "no-store" })
      .then((v) => { if (!cancelled) setText(v ?? "") })
    return () => { cancelled = true }
  }, [file.mtime, file.name, text, workspaceId])
  return [text, setText]
}

function useCopyState(): [boolean, (text: string) => Promise<void>] {
  const [copied, setCopied] = useState(false)
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text) } catch {
      const el = document.createElement("textarea")
      el.value = text; el.style.cssText = "position:fixed;opacity:0"
      document.body.appendChild(el); el.select()
      document.execCommand("copy"); document.body.removeChild(el)
    }
    setCopied(true); setTimeout(() => setCopied(false), 1500)
  }
  return [copied, copy]
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatJsonSafely(text: string): string {
  try { return hasPrecisionSensitiveJsonNumberText(text) ? text : JSON.stringify(JSON.parse(text), null, 2) }
  catch { return text }
}

function hasPrecisionSensitiveJsonNumberText(text: string): boolean {
  return /-0(?:\.0+)?(?:[eE][+-]?\d+)?|(?:\d{16,}|\d+\.\d{16,})/.test(text)
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function isSvg(file: WorkspaceFile): boolean {
  return file.mime === "image/svg+xml" || file.name.toLowerCase().endsWith(".svg")
}
