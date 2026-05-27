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
import { fetchWorkspaceFileText, workspaceRawUrl, fetchWorkspaceFilePreviewInfo, workspacePreviewPdfUrl } from "../services/workspace-files"
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
    // Check if it's a CSV file
    if (file.name.toLowerCase().endsWith(".csv")) {
      return <CsvViewer workspaceId={workspaceId} file={file} />
    }
    return <ExcelViewer workspaceId={workspaceId} file={file} />
  }
  if (file.kind === "document") return <DocxViewer workspaceId={workspaceId} file={file} />
  if (file.kind === "presentation") return <PptxViewer workspaceId={workspaceId} file={file} />
  return <BinaryViewer workspaceId={workspaceId} file={file} />
}

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
    fetchWorkspaceFileText(workspaceId, file.name, { cacheBustKey: `${file.mtime}-${reloadKey}`, cache: "no-store" }).then(
      (value) => {
        if (!cancelled) setSource(value ?? "")
      },
    )
    return () => {
      cancelled = true
    }
  }, [file.mtime, file.name, reloadKey, workspaceId])

  const previewScale = zoom / 100

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <ViewerToolbar
        left={
          <>
            <Segmented value={mode} options={["preview", "source"]} onChange={(value) => setMode(value as SourceMode)} />
            {mode === "preview" ? (
              <>
                <span className="h-5 w-px bg-border" />
                <Segmented value={viewport} options={["desktop", "tablet", "mobile"]} onChange={(value) => setViewport(value as Viewport)} />
                <span className="h-5 w-px bg-border" />
                <Segmented
                  value={String(zoom)}
                  options={["50", "75", "100", "125", "150"]}
                  labels={{ "50": "50%", "75": "75%", "100": "100%", "125": "125%", "150": "150%" }}
                  onChange={(value) => setZoom(Number(value))}
                />
              </>
            ) : null}
          </>
        }
        right={
          <>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Refresh preview" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export PDF" onClick={() => source && exportHtmlAsPdf(source, file.name)} disabled={!source}>
              <Printer className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Export PNG"
              disabled={mode !== "preview" || exportingPng}
              onClick={async () => {
                setExportingPng(true)
                try {
                  await exportIframeAsPng(iframeRef.current, file.name)
                } finally {
                  setExportingPng(false)
                }
              }}
            >
              <ImageIcon className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export Markdown" onClick={() => source && exportHtmlAsMarkdown(source, file.name)} disabled={!source}>
              <FileDown className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export ZIP" onClick={() => downloadWorkspaceArchive(workspaceId, file.name)}>
              <Archive className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8" title="Export HTML" onClick={() => source && exportHtmlAsStandaloneHtml(source, file.name)} disabled={!source}>
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
          mode === "preview" ? "p-4" : "",
          mode === "preview" ? "flex items-center justify-center" : "",
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

function SvgViewer({ workspaceId, file }: FileViewerProps) {
  const [mode, setMode] = useState<SourceMode>("preview")
  const [text, setText] = useWorkspaceText(workspaceId, file)
  const src = `${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<Segmented value={mode} options={["preview", "source"]} onChange={(value) => setMode(value as SourceMode)} />}
        right={<FileActions workspaceId={workspaceId} file={file} extra={<ReloadButton onClick={() => setText(null)} />} />}
      />
      <div className={cn("min-h-0 flex-1 overflow-auto bg-muted/30 p-5", mode === "preview" && "flex items-center justify-center")}>
        {mode === "preview" ? <img src={src} alt={file.name} className="max-h-full max-w-full rounded-md object-contain" /> : <CodeWithLines text={text ?? ""} />}
      </div>
    </div>
  )
}

function MediaViewer({ workspaceId, file }: FileViewerProps) {
  const src = workspaceRawUrl(workspaceId, file.name)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="flex min-h-0 flex-1 items-center justify-center bg-muted/30 p-5">
        {file.kind === "video" ? <video src={src} controls playsInline preload="metadata" className="max-h-full max-w-full rounded-md" /> : <audio src={src} controls preload="metadata" className="w-full max-w-xl" />}
      </div>
    </div>
  )
}

function MarkdownViewer({ workspaceId, file }: FileViewerProps) {
  const [mode, setMode] = useState<SourceMode>("preview")
  const [copied, copy] = useCopyState()
  const [text, setText] = useWorkspaceText(workspaceId, file)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar
        left={<Segmented value={mode} options={["preview", "source"]} onChange={(value) => setMode(value as SourceMode)} />}
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

function TextViewer({ workspaceId, file }: FileViewerProps) {
  const [copied, copy] = useCopyState()
  const [text, setText] = useWorkspaceText(workspaceId, file)
  const displayText = useMemo(() => (file.kind === "json" ? formatJsonSafely(text ?? "") : text ?? ""), [file.kind, text])

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

function PdfViewer({ workspaceId, file }: FileViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">PDF · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <iframe title={file.name} src={`${workspaceRawUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`} className="min-h-0 flex-1 border-0 bg-white" />
    </div>
  )
}

function ExcelViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let previewer: any = null

    const loadExcel = async () => {
      try {
        setLoading(true)
        setError(null)

        const url = workspaceRawUrl(workspaceId, file.name)
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Fetch failed: ${response.status}`)
        const arrayBuffer = await response.arrayBuffer()

        if (!cancelled && containerRef.current) {
          previewer = jsPreviewExcel.init(containerRef.current)
          await previewer.preview(arrayBuffer)
        }
      } catch (err) {
        console.error("Excel preview error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load preview")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadExcel()

    return () => {
      cancelled = true
      if (previewer) {
        previewer.destroy()
      }
    }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">Excel · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 300 }}>
        <div ref={containerRef} className="h-full w-full" style={{ minHeight: 300 }} />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Loading preview...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Preview unavailable: {error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function CsvViewer({ workspaceId, file }: FileViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])

  useEffect(() => {
    let cancelled = false

    const loadCsv = async () => {
      try {
        setLoading(true)
        setError(null)

        const url = workspaceRawUrl(workspaceId, file.name)
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Fetch failed: ${response.status}`)
        const text = await response.text()

        if (!cancelled) {
          const result = Papa.parse<string[]>(text, {
            header: false,
            skipEmptyLines: true,
          })
          const allRows = result.data as string[][]
          if (allRows.length > 0) {
            setHeaders(allRows[0])
            setRows(allRows.slice(1))
          }
        }
      } catch (err) {
        console.error("CSV preview error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load preview")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadCsv()

    return () => {
      cancelled = true
    }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">CSV · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto" style={{ minHeight: 300 }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Loading preview...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Preview unavailable: {error}</span>
          </div>
        )}
        {!loading && !error && headers.length > 0 && (
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
              <tr>
                {headers.map((header, index) => (
                  <th key={`h-${index}`} className="px-4 py-2 text-left font-medium text-foreground whitespace-nowrap">
                    {header || `Column ${index + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row, rowIndex) => (
                <tr key={`r-${rowIndex}`} className="hover:bg-muted/30">
                  {row.map((cell, cellIndex) => (
                    <td key={`c-${rowIndex}-${cellIndex}`} className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                      {cell || "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function DocxViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usePdfPreview, setUsePdfPreview] = useState<boolean>(false)

  useEffect(() => {
    let cancelled = false

    const loadDocx = async () => {
      try {
        setLoading(true)
        setError(null)

        // Step 1: Check if backend can convert it to PDF (e.g. LibreOffice is available)
        const previewInfo = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (!cancelled && previewInfo?.previewAvailable) {
          setUsePdfPreview(true)
          setLoading(false)
          return
        }

        // Step 2: Fall back to mammoth (docx only)
        const url = workspaceRawUrl(workspaceId, file.name)
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Fetch failed: ${response.status}`)
        const arrayBuffer = await response.arrayBuffer()

        if (cancelled || !containerRef.current) return

        const headerBytes = new Uint8Array(arrayBuffer.slice(0, 4))
        const isZip = headerBytes.length >= 2 && headerBytes[0] === 0x50 && headerBytes[1] === 0x4b

        if (!isZip) {
          containerRef.current.innerHTML = `
            <div class="flex h-full items-center justify-center">
              <div class="border border-dashed rounded-xl p-8 max-w-2xl text-center">
                <p class="text-xl font-bold mb-4">Preview is not available for this document</p>
                <p class="text-sm opacity-70">Only modern .docx files are supported for preview.<br/>This file appears to be a legacy .doc format, and LibreOffice is not configured on the backend.</p>
              </div>
            </div>
          `
          return
        }

        const result = await mammoth.convertToHtml(
          { arrayBuffer },
          { includeDefaultStyleMap: true },
        )

        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = result.value
        }
      } catch (err) {
        console.error("DOCX preview error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load document")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadDocx()

    return () => {
      cancelled = true
    }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">Document · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto bg-white" style={{ minHeight: 300 }}>
        {usePdfPreview ? (
          <iframe
            title={file.name}
            src={`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`}
            className="h-full w-full border-0 bg-white"
          />
        ) : (
          <div ref={containerRef} className="h-full w-full p-6 prose prose-sm max-w-none" style={{ minHeight: 500 }} />
        )}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Loading preview...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Preview unavailable: {error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function PptxViewer({ workspaceId, file }: FileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usePdfPreview, setUsePdfPreview] = useState<boolean>(false)

  useEffect(() => {
    let cancelled = false
    let pptxViewer: any = null

    const loadPptx = async () => {
      try {
        setLoading(true)
        setError(null)

        // Step 1: Check if backend can convert it to PDF (e.g. LibreOffice is available)
        const previewInfo = await fetchWorkspaceFilePreviewInfo(workspaceId, file.name)
        if (!cancelled && previewInfo?.previewAvailable) {
          setUsePdfPreview(true)
          setLoading(false)
          return
        }

        // Step 2: Fall back to pptx-preview (pptx only)
        const url = workspaceRawUrl(workspaceId, file.name)
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Fetch failed: ${response.status}`)
        const arrayBuffer = await response.arrayBuffer()

        if (!cancelled && containerRef.current) {
          // Wait for container to have real dimensions using ResizeObserver
          const el = containerRef.current
          const { width, height } = await new Promise<{ width: number; height: number }>((resolve) => {
            const check = () => {
              if (el.clientWidth > 0 && el.clientHeight > 0) {
                resolve({ width: el.clientWidth, height: el.clientHeight })
                return true
              }
              return false
            }
            if (check()) return
            const ro = new ResizeObserver(() => {
              if (check()) ro.disconnect()
            })
            ro.observe(el)
            // Safety timeout after 2s — use fallback dimensions
            setTimeout(() => {
              ro.disconnect()
              resolve({ width: el.clientWidth || 800, height: el.clientHeight || 600 })
            }, 2000)
          })

          if (cancelled || !containerRef.current) return
          pptxViewer = initPptxPreview(containerRef.current, { width, height })
          await pptxViewer.preview(arrayBuffer)
        }
      } catch (err) {
        console.error("PPTX preview error:", err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load presentation")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadPptx()

    return () => {
      cancelled = true
      if (pptxViewer) {
        pptxViewer.destroy()
      }
    }
  }, [file.name, file.mtime, workspaceId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">Presentation · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="relative flex-1 overflow-auto bg-white" style={{ minHeight: 300 }}>
        {usePdfPreview ? (
          <iframe
            title={file.name}
            src={`${workspacePreviewPdfUrl(workspaceId, file.name)}?v=${Math.round(file.mtime)}`}
            className="h-full w-full border-0 bg-white"
          />
        ) : (
          <div ref={containerRef} className="h-full w-full ppt-previewer" style={{ minHeight: 500 }} />
        )}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Loading preview...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <span className="text-sm text-muted-foreground">Preview unavailable: {error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

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

function ViewerToolbar({ left, right }: { left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-11 shrink-0 items-center justify-between gap-3 border-b px-3 py-1">
      <div className="flex min-w-0 flex-wrap items-center gap-1">{left}</div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">{right}</div>
    </div>
  )
}

function FileActions({ workspaceId, file, extra }: { workspaceId: string; file: WorkspaceFile; extra?: React.ReactNode }) {
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
  const numbered = text.split("\n").map((line, index) => (
    <div key={`${index}-${line}`} className="grid grid-cols-[3rem_1fr] gap-3">
      <span className="select-none text-right text-muted-foreground">{index + 1}</span>
      <span className="whitespace-pre-wrap break-words">{line || " "}</span>
    </div>
  ))
  return <pre className="h-full overflow-auto p-4 text-xs leading-6">{numbered}</pre>
}

function useWorkspaceText(workspaceId: string, file: WorkspaceFile): [string | null, (value: string | null) => void] {
  const [text, setText] = useState<string | null>(null)
  useEffect(() => {
    if (text !== null) return
    let cancelled = false
    fetchWorkspaceFileText(workspaceId, file.name, { cacheBustKey: file.mtime, cache: "no-store" }).then((value) => {
      if (!cancelled) setText(value ?? "")
    })
    return () => {
      cancelled = true
    }
  }, [file.mtime, file.name, text, workspaceId])
  return [text, setText]
}

function useCopyState(): [boolean, (text: string) => Promise<void>] {
  const [copied, setCopied] = useState(false)
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const textarea = document.createElement("textarea")
      textarea.value = text
      textarea.style.position = "fixed"
      textarea.style.opacity = "0"
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand("copy")
      document.body.removeChild(textarea)
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }
  return [copied, copy]
}

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
