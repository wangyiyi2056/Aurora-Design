import { useRef, useState, useEffect, useCallback } from "react"
import { Maximize2, Minimize2, Download } from "lucide-react"

interface HtmlPreviewProps {
  html: string
  maxHeight?: number
}

export function HtmlPreview({ html, maxHeight = 600 }: HtmlPreviewProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(maxHeight)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const handleResize = useCallback(() => {
    try {
      const body = iframeRef.current?.contentWindow?.document?.body
      if (body) {
        const h = body.scrollHeight + 40
        setHeight(Math.min(h, maxHeight))
      }
    } catch {
      // cross-origin, ignore
    }
  }, [maxHeight])

  const srcDoc = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;padding:16px;font-family:system-ui,-apple-system,sans-serif}</style>
</head>
<body>${html}</body>
</html>`

  const downloadHtml = () => {
    const blob = new Blob([html], { type: "text/html" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "report.html"
    a.click()
    URL.revokeObjectURL(url)
  }

  useEffect(() => {
    const el = iframeRef.current
    if (!el) return
    el.addEventListener("load", handleResize)
    return () => el.removeEventListener("load", handleResize)
  }, [handleResize])

  if (!html) return null

  return (
    <div
      className="my-3 rounded-xl overflow-hidden border border-border/60 bg-surface"
      style={isFullscreen ? {
        position: "fixed",
        inset: 0,
        zIndex: 50,
        borderRadius: 0,
      } : undefined}
    >
      <div className="flex items-center justify-between px-4 py-2 bg-surface-elevated/50 border-b border-border/30">
        <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">
          Report Preview
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={downloadHtml}
            className="p-1.5 rounded-md hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            title="Download HTML"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 rounded-md hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
      <iframe
        ref={iframeRef}
        srcDoc={srcDoc}
        sandbox="allow-scripts allow-same-origin"
        title="HTML Preview"
        className="w-full border-0"
        style={{ height: isFullscreen ? "calc(100% - 41px)" : height }}
      />
    </div>
  )
}
