import { Markdown } from "../runtime/markdown"

interface MessageRendererProps {
  content: string
}

export default function MessageRenderer({ content }: MessageRendererProps) {
  return <Markdown content={content} />
}
