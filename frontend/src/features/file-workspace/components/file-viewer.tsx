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

// ─── Shared DOCX iframe styles ────────────────────────────────────────────────
// Injected into iframe srcDoc so mammoth-rendered HTML is fully isolated from
// Tailwind's CSS reset — no @tailwindcss/typography needed.
const DOCX_IFRAME_STYLE = `
  body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    color: #1a1a1a;
    padding: 1.5rem 2.5rem;
    margin: 0;
    max-width: 860px;
  }
  p { margin-bottom: 0.6rem; }
  h1 { font-size: 1.6rem; font-weight: 700; margin: 1.2rem 0 0.6rem; }
  h2 { font-size: 1.3rem; font-weight: 600; margin: 1rem 0 0.5rem; }
  h3 { font-size: 1.1rem; font-weight: 600; margin: 0.9rem 0 0.4rem; }
  h4, h5, h6 { font-weight: 600; margin: 0.8rem 0 0.4rem; }
  ul, ol { padding-left: 1.5rem; margin-bottom: 0.6rem; }
  li { margin-bottom: 0.25rem; }
  strong, b { font-weight: 600; }
  em, i { font-style: italic; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
  td, th { border: 1px solid #ddd; padding: 6px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  img { max-width: 100%; height: auto; }
  a { color: #2563eb; text-decoration: underline; }
  blockquote {
    border-left: 3px solid #ddd;
    margin: 0.75rem 0;
    padding: 0.25rem 1rem;
    color: #555;
  }
  code {
    background: #f1f1f1;
    border-radius: 3px;
    padding: 0.1em 0.35em;
    font-size: 0.9em;
    font-family: monospace;
  }
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
    if (file.name.toLowerCase().endsWith(".csv")) {
      return <CsvViewer workspaceId={workspaceId} file={file} />
    }
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
    }).then((value) => {
      if (!cancelled) setSource(value ?? "")
    })
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
                <Segmented
                  value={viewport}
                  options={["desktop", "tablet", "mobile"]}
                  onChange={(v) => setViewport(v as Viewport)}
                />
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
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Refresh preview" onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Export PDF" disabled={!source}
              onClick={() => source && exportHtmlAsPdf(source, file.name)}
            >
              <Printer className="h-4 w-4" />
            </Button>
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Export PNG" disabled={mode !== "preview" || exportingPng}
              onClick={async () => {
                setExportingPng(true)
                try { await exportIframeAsPng(iframeRef.current, file.name) }
                finally { setExportingPng(false) }
              }}
            >
              <ImageIcon className="h-4 w-4" />
            </Button>
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Export Markdown" disabled={!source}
              onClick={() => source && exportHtmlAsMarkdown(source, file.name)}
            >
              <FileDown className="h-4 w-4" />
            </Button>
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Export ZIP"
              onClick={() => downloadWorkspaceArchive(workspaceId, file.name)}
            >
              <Archive className="h-4 w-4" />
            </Button>
            <Button
              type="button" variant="ghost" size="icon" className="h-8 w-8"
              title="Export HTML" disabled={!source}
              onClick={() => source && exportHtmlAsStandaloneHtml(source, file.name)}
            >
              <Download className="h-4 w-4" />
            </Button>
            <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Open in new tab">
              <a href={src} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          </>
        }
      />
      <div
        className={cn(
          "min-h-0 flex-1 overflow-auto bg-muted/30",
          mode === "preview" ? "p-4 flex items-center justify-center" : "",
        )}
      >
        {mode === "source" ? (
          <CodeWithLines text={source ?? ""} />
        ) : (
          <div
            className="mx-auto"
            style={{
              transform: `scale(${previewScale})`,
              transformOrigin: "center center",
              width: `${100 / previewScale}%`,
              height: `${100 / previewScale}%`,
              minHeight: `${520 / previewScale}px`,
            }}
          >
            <iframe
              ref={iframeRef}
              key={src}
              title={file.name}
              src={src}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
              className={cn("mx-auto h-full rounded-md border bg-white", viewportClass[viewport])}
            />
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
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
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
        {mode === "preview"
          ? <img src={src} alt={file.name} className="max-h-full max-w-full rounded-md object-contain" />
          : <CodeWithLines text={text ?? ""} />
        }
      </div>
    </div>
  )
}

// ─── Media Viewer ─────────────────────────────────────────────────────────────
function MediaViewer({ workspaceId, file }: FileViewerProps) {
  const src = workspaceRawUrl(workspaceId, file.name)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <div className="flex min-h-0 flex-1 items-center justify-center bg-muted/30 p-5">
        {file.kind === "video"
          ? <video src={src} controls playsInline preload="metadata" className="max-h-full max-w-full rounded-md" />
          : <audio src={src} controls preload="metadata" className="w-full max-w-xl" />
        }
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
        right={
          <>
            <ReloadButton onClick={() => setText(null)} />
            <CopyButton copied={copied} onClick={() => copy(text ?? "")} />
            <FileActions workspaceId={workspaceId} file={file} />
          </>
        }
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
  const displayText = useMemo(
    () => (file.kind === "json" ? formatJsonSafely(text ?? "") : text ?? ""),
    [file.kind, text],
  )
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>}
        right={
          <>
            <ReloadButton onClick={() => setText(null)} />
            <CopyButton copied={copied} onClick={() => copy(displayText)} />
            <FileActions workspaceId={workspaceId} file={file} />
          </>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto">
        <CodeWithLines text={displayText} />
      </div>
    </div>
  )
}

// ─── PDF Viewer ───────────────────────────────────────────────────────────────
function PdfViewer({ workspaceId, file }: FileViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">PDF · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <iframe
        title={file.name}
        src={`${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`}
        className="min-h-0 flex-1 border-0 bg-white"
      />
    </div>
  )
}

// ─── Excel Viewer ─────────────────────────────────────────────────────────────
// Uses @js-preview/excel. Promise-chain error handling borrowed from ragflow.
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
        if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
        const arrayBuffer = await res.arrayBuffer()

        if (cancelled || !containerRef.current) return
        previewer = jsPreviewExcel.init(containerRef.current)
        previewer
          .preview(arrayBuffer)
          .then(() => { if (!cancelled) setLoading(false) })
          .catch((e: unknown) => {
            console.warn("Excel preview failed:", e)
            previewer?.destroy()
            if (!cancelled) { setError("Preview unavailable for this file"); setLoading(false) }
          })
      } catch (err) {
        console.error("Excel load error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load")
          setLoading(false)
        }
      }
    }

    load()
    return () => { cancelled = true; previewer?.destroy() }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">Excel · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 320 }}>
        <div ref={containerRef} className="h-full w-full" style={{ minHeight: 320 }} />
        <ViewerOverlay loading={loading} error={error} />
      </div>
    </div>
  )
}

// ─── CSV Viewer ───────────────────────────────────────────────────────────────
// ragflow approach: fetch blob → FileReader.readAsText for encoding reliability.
function CsvViewer({ workspaceId, file }: FileViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        setLoading(true)
        setError(null)

        const res = await fetch(workspaceRawUrl(workspaceId, file.name))
        if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
        const blob = await res.blob()

        // FileReader gives consistent encoding handling across browsers (ragflow pattern)
        const text = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.readAsText(blob)
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(reader.error)
        })

        if (cancelled) return

        const result = Papa.parse<string[]>(text, { header: false, skipEmptyLines: false })
        const allRows = result.data as string[][]
        if (allRows.length > 0) {
          setHeaders(allRows[0])
          setRows(allRows.slice(1))
        }
      } catch (err) {
        console.error("CSV load error:", err)
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">CSV · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 320 }}>
        <ViewerOverlay loading={loading} error={error} />
        {!loading && !error && headers.length > 0 && (
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
              <tr>
                {headers.map((h, i) => (
                  <th key={i} className="px-4 py-2 text-left font-medium text-foreground whitespace-nowrap">
                    {h || `Column ${i + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row, ri) => (
                <tr key={ri} className="hover:bg-muted/30">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                      {cell || "–"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && !error && headers.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            File is empty
          </div>
        )}
      </div>
    </div>
  )
}

// ─── DOCX Viewer ──────────────────────────────────────────────────────────────
// ragflow approach:
//  1. Check backend PDF conversion (LibreOffice) first.
//  2. Fetch as blob, probe ZIP magic bytes to detect docx vs legacy doc.
//  3. Convert with mammoth, render inside an iframe with srcDoc so the HTML
//     is fully isolated from Tailwind's CSS reset — no typography plugin needed.
function DocxViewer({ workspaceId, file }: FileViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [htmlContent, setHtmlContent] = useState<string>("")
  const [usePdfPreview, setUsePdfPreview] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        setLoading(true)
        setError(null)

        // Step 1 — try backend LibreOffice PDF conversion
        const previewInfo = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (!cancelled && previewInfo?.previewAvailable) {
          setUsePdfPreview(true)
          setLoading(false)
          return
        }

        // Step 2 — fetch as blob and probe ZIP magic bytes (ragflow pattern)
        const res = await fetch(workspaceRawUrl(workspaceId, file.name))
        if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
        const blob = await res.blob()
        if (cancelled) return

        const headerBuf = await blob.slice(0, 4).arrayBuffer()
        const hdr = new Uint8Array(headerBuf)
        const isZip = hdr.length >= 2 && hdr[0] === 0x50 && hdr[1] === 0x4b

        if (!isZip) {
          // Legacy .doc (CFBF binary) — mammoth cannot handle it
          if (!cancelled) {
            setHtmlContent(`
              <div style="display:flex;height:100%;min-height:300px;align-items:center;justify-content:center;padding:2rem">
                <div style="border:1px dashed #ccc;border-radius:12px;padding:2rem;max-width:480px;text-align:center">
                  <p style="font-size:1rem;font-weight:600;margin-bottom:0.75rem">Preview not available</p>
                  <p style="font-size:0.85rem;opacity:0.65;line-height:1.6">
                    Only modern <code>.docx</code> files are supported.<br/>
                    This appears to be a legacy <code>.doc</code> format.<br/>
                    Please download the file to view it.
                  </p>
                </div>
              </div>
            `)
            setLoading(false)
          }
          return
        }

        // Step 3 — ZIP-like payload: convert with mammoth
        const arrayBuffer = await blob.arrayBuffer()
        const result = await mammoth.convertToHtml(
          { arrayBuffer },
          { includeDefaultStyleMap: true },
        )

        if (!cancelled) {
          setHtmlContent(result.value)
          setLoading(false)
        }
      } catch (err) {
        console.error("DOCX load error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load document")
          setLoading(false)
        }
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
        {usePdfPreview && (
          <iframe
            title={file.name}
            src={`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`}
            className="absolute inset-0 h-full w-full border-0"
          />
        )}
        {/* iframe srcDoc fully isolates mammoth HTML from Tailwind resets */}
        {!usePdfPreview && htmlContent && !loading && (
          <iframe
            title={file.name}
            srcDoc={`<!doctype html><html><head><meta charset="utf-8"><style>${DOCX_IFRAME_STYLE}</style></head><body>${htmlContent}</body></html>`}
            className="absolute inset-0 h-full w-full border-0 bg-white"
          />
        )}
        <ViewerOverlay loading={loading} error={error} />
      </div>
    </div>
  )
}

// ─── PPTX Viewer ──────────────────────────────────────────────────────────────
// ragflow approach:
//  • containerRef wraps the whole area — its clientWidth/clientHeight are reliable
//    because it has a fixed minHeight (600px), so pptx-preview gets real dimensions.
//  • wrapperRef is the actual render target passed to initPptxPreview, kept separate
//    so the layout container is not mutated by the library.
function PptxViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usePdfPreview, setUsePdfPreview] = useState(false)

  useEffect(() => {
    let cancelled = false
    let viewer: any = null

    const load = async () => {
      try {
        setLoading(true)
        setError(null)

        // Step 1 — try backend LibreOffice PDF conversion
        const previewInfo = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (!cancelled && previewInfo?.previewAvailable) {
          setUsePdfPreview(true)
          setLoading(false)
          return
        }

        // Step 2 — fetch and pass to pptx-preview
        const res = await fetch(workspaceRawUrl(workspaceId, file.name))
        if (!res.ok) throw new Error(`Fetch failed: ${res.status}`)
        const arrayBuffer = await res.arrayBuffer()

        if (!cancelled && containerRef.current && wrapperRef.current) {
          // containerRef has minHeight:600 so clientWidth/Height are real values here
          const width = (containerRef.current.clientWidth || 860) - 50
          const height = (containerRef.current.clientHeight || 650) - 50

          viewer = initPptxPreview(wrapperRef.current, { width, height })
          await viewer.preview(arrayBuffer)
        }
      } catch (err) {
        console.error("PPTX load error:", err)
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load presentation")
      } finally {
        if (!cancelled) setLoading(false)
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
      {/* containerRef: fixed minHeight gives reliable clientHeight for pptx-preview init */}
      <div ref={containerRef} className="relative flex-1 overflow-auto ppt-previewer" style={{ minHeight: 600 }}>
        {usePdfPreview ? (
          <iframe
            title={file.name}
            src={`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`}
            className="absolute inset-0 h-full w-full border-0"
          />
        ) : (
          <div className="overflow-auto p-2">
            <div className="flex flex-col gap-4">
              {/* wrapperRef: separate render target for pptx-preview library */}
              <div ref={wrapperRef} />
            </div>
          </div>
        )}
        <ViewerOverlay loading={loading} error={error} />
      </div>
    </div>
  )
}

// ─── Binary Viewer ────────────────────────────────────────────────────────────
function BinaryViewer({ workspaceId, file }: FileViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<span className="text-xs text-muted-foreground">binary · {humanSize(file.size)}</span>}
        right={<FileActions workspaceId={workspaceId} file={file} />}
      />
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md rounded-lg border bg-card p-5 text-center">
          <FileQuestion className="mx-auto h-8 w-8 text-muted-foreground" />
          <h3 className="mt-3 text-sm font-semibold">{file.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Preview is unavailable for this file type. Size: {humanSize(file.size)}
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Shared UI primitives ─────────────────────────────────────────────────────

function ViewerToolbar({ left, right }: { left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-11 shrink-0 items-center justify-between gap-3 border-b px-3 py-1">
      <div className="flex min-w-0 flex-wrap items-center gap-1">{left}</div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">{right}</div>
    </div>
  )
}

/** Shared loading / error overlay — requires parent to have `position: relative` */
function ViewerOverlay({ loading, error }: { loading: boolean; error: string | null }) {
  if (!loading && !error) return null
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm pointer-events-none">
      {loading && <span className="text-sm text-muted-foreground animate-pulse">Loading preview…</span>}
      {!loading && error && (
        <span className="text-sm text-destructive">Preview unavailable: {error}</span>
      )}
    </div>
  )
}

function FileActions({
  workspaceId,
  file,
  extra,
}: {
  workspaceId: string
  file: WorkspaceFile
  extra?: React.ReactNode
}) {
  return (
    <>
      {extra}
      <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Download">
        <a href={workspaceRawUrl(workspaceId, file.name)} download>
          <Download className="h-4 w-4" />
        </a>
      </Button>
      <Button asChild variant="ghost" size="icon" className="h-8 w-8" title="Open in new tab">
        <a href={workspaceRawUrl(workspaceId, file.name)} target="_blank" rel="noreferrer">
          <ExternalLink className="h-4 w-4" />
        </a>
      </Button>
    </>
  )
}

function Segmented({
  value,
  options,
  labels,
  onChange,
}: {
  value: string
  options: string[]
  labels?: Record<string, string>
  onChange: (value: string) => void
}) {
  return (
    <div className="flex items-center gap-1 rounded-md border bg-muted/50 p-0.5">
      {options.map((item) => (
        <button
          key={item}
          type="button"
          aria-pressed={value === item}
          className={cn(
            "h-7 rounded-[5px] px-2 text-xs font-medium capitalize transition-colors",
            value === item
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:bg-background hover:text-foreground",
          )}
          onClick={() => onChange(item)}
        >
          {labels?.[item] ?? item}
        </button>
      ))}
    </div>
  )
}

function ReloadButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Reload from disk" onClick={onClick}>
      <RefreshCw className="h-4 w-4" />
    </Button>
  )
}

function CopyButton({ copied, onClick }: { copied: boolean; onClick: () => void }) {
  return (
    <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Copy" onClick={onClick}>
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </Button>
  )
}

function CodeWithLines({ text }: { text: string }) {
  const lines = text.split("\n")
  return (
    <pre className="h-full overflow-auto p-4 text-xs leading-6">
      {lines.map((line, i) => (
        <div key={i} className="grid grid-cols-[3rem_1fr] gap-3">
          <span className="select-none text-right text-muted-foreground">{i + 1}</span>
          <span className="whitespace-pre-wrap break-words">{line || " "}</span>
        </div>
      ))}
    </pre>
  )
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

function useWorkspaceText(
  workspaceId: string,
  file: WorkspaceFile,
): [string | null, (value: string | null) => void] {
  const [text, setText] = useState<string | null>(null)
  useEffect(() => {
    if (text !== null) return
    let cancelled = false
    fetchWorkspaceFileText(workspaceId, file.name, {
      cacheBustKey: file.mtime,
      cache: "no-store",
    }).then((value) => { if (!cancelled) setText(value ?? "") })
    return () => { cancelled = true }
  }, [file.mtime, file.name, text, workspaceId])
  return [text, setText]
}

function useCopyState(): [boolean, (text: string) => Promise<void>] {
  const [copied, setCopied] = useState(false)
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const el = document.createElement("textarea")
      el.value = text
      el.style.cssText = "position:fixed;opacity:0"
      document.body.appendChild(el)
      el.select()
      document.execCommand("copy")
      document.body.removeChild(el)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return [copied, copy]
}

// ─── Pure helpers ─────────────────────────────────────────────────────────────

function formatJsonSafely(text: string): string {
  try {
    if (hasPrecisionSensitiveJsonNumberText(text)) return text
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
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
