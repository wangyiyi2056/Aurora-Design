import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import { HtmlPreview } from "./html-preview"

interface MessageRendererProps {
  content: string
}

export default function MessageRenderer({ content }: MessageRendererProps) {
  return (
    <div className="message-content">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "")
          const language = match ? match[1] : "text"
          const codeString = String(children).replace(/\n$/, "")

          if (language === "html" || language === "web") {
            return <HtmlPreview html={codeString} />
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
    </div>
  )
}
