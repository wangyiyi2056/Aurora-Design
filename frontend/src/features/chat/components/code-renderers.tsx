import type { Components } from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import DOMPurify from "dompurify"
import { ChartRenderer } from "./chart-renderer"
import { HtmlPreview } from "./html-preview"
import { AlertCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ChartData {
  type: string
  sql?: string
  data?: Record<string, unknown>[]
  config?: Record<string, unknown>
}

interface DashboardData {
  charts?: ChartData[]
  title?: string
  layout?: string
}

interface ThinkingData {
  content?: string
  steps?: string[]
  conclusion?: string
}

interface PluginData {
  name?: string
  description?: string
  status?: "success" | "error" | "running"
  result?: unknown
}

interface DbChartData {
  chart_type?: string
  sql?: string
  data?: Record<string, unknown>[]
  title?: string
  description?: string
}

interface ApiResponseData {
  success?: boolean
  message?: string
  data?: unknown
  error?: string
}

// Parse JSON content safely
function parseJSONContent<T>(content: string, fallback: T): T {
  try {
    return JSON.parse(content) as T
  } catch {
    return fallback
  }
}

// Language renderer for vis-chart
function VisChartRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<ChartData>(content, { type: "bar" })

  return <ChartRenderer data={data} className="my-2" />
}

// Language renderer for vis-dashboard
function VisDashboardRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<DashboardData>(content, {})

  if (!data.charts || data.charts.length === 0) {
    return (
      <div className="glass-effect rounded-xl p-4 my-2">
        <div className="flex items-center justify-center h-[150px] text-muted-foreground">
          <AlertCircle className="h-5 w-5 mr-2 opacity-50" />
          <span>No dashboard data available</span>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-effect rounded-xl p-4 my-2">
      {data.title && (
        <h3 className="text-lg font-semibold mb-4 text-foreground">{data.title}</h3>
      )}
      <div className={cn(
        "grid gap-4",
        data.layout === "grid-2" ? "grid-cols-2" :
        data.layout === "grid-3" ? "grid-cols-3" :
        "grid-cols-1"
      )}>
        {data.charts.map((chart, index) => (
          <ChartRenderer key={index} data={chart} />
        ))}
      </div>
    </div>
  )
}

// Language renderer for vis-thinking
function VisThinkingRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<ThinkingData>(content, {})

  // If it's raw text thinking content (not JSON), display as collapsible
  if (!data.steps && !data.conclusion) {
    return (
      <div className="thinking-block rounded-xl p-3 my-2 bg-muted/30 border border-border/40">
        <details className="group">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin opacity-50" />
            Thinking process...
          </summary>
          <div className="mt-3 pl-4 text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {content}
          </div>
        </details>
      </div>
    )
  }

  return (
    <div className="thinking-block rounded-xl p-3 my-2 bg-muted/30 border border-border/40">
      {data.steps && data.steps.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-4 w-4 opacity-50" />
            Reasoning Steps
          </div>
          <ul className="pl-4 space-y-1">
            {data.steps.map((step, index) => (
              <li key={index} className="text-sm text-muted-foreground list-disc">
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.conclusion && (
        <div className="mt-3 pt-3 border-t border-border/30 text-sm text-foreground">
          <strong>Conclusion:</strong> {data.conclusion}
        </div>
      )}
    </div>
  )
}

// Language renderer for vis-db-chart
function VisDbChartRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<DbChartData>(content, {})

  // Map chart_type to ChartRenderer format
  const chartData: ChartData = {
    type: data.chart_type || "bar",
    sql: data.sql,
    data: data.data,
  }

  return (
    <div className="my-2">
      {data.title && (
        <h4 className="text-sm font-medium mb-2 text-foreground">{data.title}</h4>
      )}
      <ChartRenderer data={chartData} />
    </div>
  )
}

// Language renderer for vis-plugin
function VisPluginRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<PluginData>(content, {})

  const statusColors = {
    success: "text-green-500 border-green-500/30 bg-green-500/10",
    error: "text-destructive border-destructive/30 bg-destructive/10",
    running: "text-primary border-primary/30 bg-primary/10",
  }

  return (
    <div className={cn(
      "rounded-xl p-3 my-2 border",
      statusColors[data.status || "running"]
    )}>
      {data.name && (
        <div className="flex items-center gap-2 text-sm font-medium">
          {data.status === "running" && <Loader2 className="h-4 w-4 animate-spin" />}
          {data.status === "error" && <AlertCircle className="h-4 w-4" />}
          {data.status === "success" && <span className="h-4 w-4 text-green-500">+</span>}
          <span>{data.name}</span>
        </div>
      )}
      {data.description && (
        <p className="text-sm text-muted-foreground mt-1">{data.description}</p>
      )}
      {data.result !== undefined && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <span className="text-xs text-muted-foreground">Result: </span>
          <code className="text-xs bg-muted/50 px-1 rounded">
            {typeof data.result === "object" ? JSON.stringify(data.result) : String(data.result)}
          </code>
        </div>
      )}
    </div>
  )
}

// Language renderer for vis-api-response
function VisApiResponseRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  const data = parseJSONContent<ApiResponseData>(content, {})

  if (data.success) {
    return (
      <div className="rounded-xl p-3 my-2 border border-green-500/30 bg-green-500/10">
        <div className="flex items-center gap-2 text-sm font-medium text-green-500">
          <span className="h-4 w-4">+</span>
          <span>API Response Success</span>
        </div>
        {data.message && (
          <p className="text-sm text-muted-foreground mt-1">{data.message}</p>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-xl p-3 my-2 border border-destructive/30 bg-destructive/10">
      <div className="flex items-center gap-2 text-sm font-medium text-destructive">
        <AlertCircle className="h-4 w-4" />
        <span>API Response Error</span>
      </div>
      {data.error && (
        <p className="text-sm text-destructive/80 mt-1">{data.error}</p>
      )}
    </div>
  )
}

// Language renderer for vis-convert-error
function VisConvertErrorRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")

  return (
    <div className="rounded-xl p-3 my-2 border border-destructive/50 bg-destructive/10">
      <div className="flex items-center gap-2 text-sm font-medium text-destructive">
        <AlertCircle className="h-4 w-4" />
        <span>Visualization Error</span>
      </div>
      <div className="mt-2 text-sm text-muted-foreground">
        Failed to render visualization. Raw content:
      </div>
      <SyntaxHighlighter
        language="json"
        style={vscDarkPlus}
        PreTag="div"
        className="!bg-transparent !m-0 text-xs mt-1"
      >
        {content}
      </SyntaxHighlighter>
    </div>
  )
}

// Language renderer for web/html
function WebRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  return <HtmlPreview html={content} />
}

// Language renderer for svg - sanitized with DOMPurify to prevent XSS
function SvgRenderer({ children }: { className?: string; children: React.ReactNode }) {
  const content = String(children).replace(/\n$/, "")
  // Sanitize SVG content to prevent XSS attacks
  const sanitized = DOMPurify.sanitize(content, {
    USE_PROFILES: { svg: true, svgFilters: true },
    ADD_TAGS: ['svg', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'text', 'g', 'defs', 'use'],
  })
  return (
    <div className="my-2 overflow-auto rounded-lg border border-border/40 bg-white dark:bg-slate-900 p-4">
      <div dangerouslySetInnerHTML={{ __html: sanitized }} className="max-w-full" />
    </div>
  )
}

// Default code renderer for regular languages
function DefaultCodeRenderer({
  className,
  children,
  ...props
}: {
  className?: string
  children: React.ReactNode
}) {
  const match = /language-(\w+)/.exec(className || "")
  const language = match ? match[1] : "text"
  const codeString = String(children).replace(/\n$/, "")

  // Inline code
  if (!match) {
    return (
      <code
        className="bg-muted/50 px-1.5 py-0.5 rounded text-sm font-mono text-foreground"
        {...props}
      >
        {children}
      </code>
    )
  }

  return (
    <SyntaxHighlighter
      style={vscDarkPlus}
      language={language}
      PreTag="div"
      className="rounded-lg text-sm my-2"
      {...(props as Record<string, unknown>)}
    >
      {codeString}
    </SyntaxHighlighter>
  )
}

// Language renderer registry
export const languageRenderers: Record<string, (props: { className?: string; children: React.ReactNode }) => JSX.Element> = {
  "vis-chart": VisChartRenderer,
  "vis-dashboard": VisDashboardRenderer,
  "vis-thinking": VisThinkingRenderer,
  "vis-db-chart": VisDbChartRenderer,
  "vis-plugin": VisPluginRenderer,
  "vis-api-response": VisApiResponseRenderer,
  "vis-convert-error": VisConvertErrorRenderer,
  "html": WebRenderer,
  "web": WebRenderer,
  "svg": SvgRenderer,
}

// Get code components for ReactMarkdown
export function getCodeComponents(): Partial<Components> {
  return {
    code({ className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || "")
      const language = match ? match[1] : undefined

      // Check if we have a custom renderer for this language
      if (language && languageRenderers[language]) {
        return languageRenderers[language]({ className, children })
      }

      // Check for SVG in XML content
      if (language === "xml") {
        const content = String(children).replace(/\n$/, "")
        if (content.includes("<svg") && content.includes("</svg>")) {
          return <SvgRenderer className={className} children={children} />
        }
      }

      // Use default renderer
      return DefaultCodeRenderer({ className, children, ...props })
    },
  }
}

// Export individual renderers for direct use
export {
  VisChartRenderer,
  VisDashboardRenderer,
  VisThinkingRenderer,
  VisDbChartRenderer,
  VisPluginRenderer,
  VisApiResponseRenderer,
  VisConvertErrorRenderer,
  WebRenderer,
  SvgRenderer,
  DefaultCodeRenderer,
}