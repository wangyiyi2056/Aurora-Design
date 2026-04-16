import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import { VisChart } from "../../../components/vis/vis-chart"
import { VisDashboard } from "../../../components/vis/vis-dashboard"

interface MessageRendererProps {
  content: string
}

interface VisChartData {
  sql?: string
  type: string
  title?: string
  describe?: string
  data: Record<string, unknown>[]
}

interface VisDashboardData {
  data: {
    sql?: string
    type: string
    title?: string
    describe?: string
    data: Record<string, unknown>[]
    err_msg?: string | null
  }[]
  chart_count?: number
  title?: string
}

function tryParseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function VisBlock({ language, codeString }: { language: string; codeString: string }) {
  if (language === "vis-db-chart") {
    const data = tryParseJson(codeString) as VisChartData | null
    if (!data || !Array.isArray(data.data)) {
      return <div className="text-sm text-text-secondary">Invalid chart data</div>
    }
    return (
      <VisChart
        data={data.data}
        type={data.type}
        title={data.title}
        sql={data.sql}
      />
    )
  }

  if (language === "vis-dashboard") {
    const data = tryParseJson(codeString) as VisDashboardData | null
    if (!data || !Array.isArray(data.data)) {
      return <div className="text-sm text-text-secondary">Invalid dashboard data</div>
    }
    return <VisDashboard charts={data.data} title={data.title} />
  }

  return null
}

export default function MessageRenderer({ content }: MessageRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "")
          const language = match ? match[1] : "text"
          const codeString = String(children).replace(/\n$/, "")

          if (language === "vis-db-chart" || language === "vis-dashboard") {
            return <VisBlock language={language} codeString={codeString} />
          }

          return (
            <SyntaxHighlighter
              style={vscDarkPlus}
              language={language}
              PreTag="div"
              className="rounded-lg text-sm my-2"
              {...(props as any)}
            >
              {codeString}
            </SyntaxHighlighter>
          )
        },
        p({ children }) {
          return <p className="m-0 leading-relaxed">{children}</p>
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 my-2">{children}</ul>
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 my-2">{children}</ol>
        },
        li({ children }) {
          return <li className="my-1">{children}</li>
        },
        table({ children }) {
          return (
            <div className="overflow-auto my-2">
              <table className="w-full text-sm border-collapse border border-border">
                {children}
              </table>
            </div>
          )
        },
        thead({ children }) {
          return <thead className="bg-surface-elevated">{children}</thead>
        },
        th({ children }) {
          return (
            <th className="border border-border px-3 py-2 text-left font-semibold">
              {children}
            </th>
          )
        },
        td({ children }) {
          return (
            <td className="border border-border px-3 py-2">{children}</td>
          )
        },
        hr() {
          return <hr className="border-border my-4" />
        },
        a({ children, href }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline hover:no-underline"
            >
              {children}
            </a>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
