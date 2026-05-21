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
import { fetchWorkspaceFileText, workspaceRawUrl } from "../services/workspace-files"
import type { WorkspaceFile } from "../types"

interface FileViewerProps {
  workspaceId: string
  file: WorkspaceFile
}

interface WorkspacePreviewResponse {
  title: string
  sections: Array<{ title: string; lines: string[] }>
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
  if (file.kind === "pdf" || file.kind === "document" || file.kind === "presentation" || file.kind === "spreadsheet") {
    return <DocumentPreviewViewer workspaceId={workspaceId} file={file} />
  }
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

function DocumentPreviewViewer({ workspaceId, file }: FileViewerProps) {
  const [preview, setPreview] = useState<WorkspacePreviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/files/${file.name.split("/").map(encodeURIComponent).join("/")}/preview`)
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((value) => {
        if (!cancelled) setPreview(value as WorkspacePreviewResponse | null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [file.name, file.mtime, workspaceId])

  if (file.kind === "pdf") {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <ViewerToolbar left={<span className="text-xs text-muted-foreground">PDF · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
        <iframe title={file.name} src={workspaceRawUrl(workspaceId, file.name)} className="min-h-0 flex-1 border-0 bg-white" />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ViewerToolbar left={<span className="text-xs text-muted-foreground">{file.kind} · {humanSize(file.size)}</span>} right={<FileActions workspaceId={workspaceId} file={file} />} />
      <div className="min-h-0 flex-1 overflow-auto p-6">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading preview...</div>
        ) : preview ? (
          <div className="mx-auto max-w-3xl space-y-5">
            <h2 className="text-lg font-semibold">{preview.title}</h2>
            {preview.sections.map((section, index) => (
              <section key={`${section.title}-${index}`} className="rounded-md border p-4">
                <h3 className="text-sm font-semibold">{section.title}</h3>
                <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                  {section.lines.map((line, lineIndex) => <p key={`${lineIndex}-${line}`}>{line}</p>)}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">Preview unavailable.</div>
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
