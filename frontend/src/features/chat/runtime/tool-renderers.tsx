import type { ReactNode } from "react"

import type { ToolPart, ToolStatus } from "@/stores/chat-store"

export interface ToolRenderProps {
  status: ToolStatus
  name: string
  input?: Record<string, unknown>
  output?: string
  error?: string
}

export type ToolRenderer = (props: ToolRenderProps) => ReactNode

const renderers = new Map<string, ToolRenderer>()

export function registerToolRenderer(name: string, renderer: ToolRenderer): () => void {
  renderers.set(name.toLowerCase(), renderer)
  return () => {
    if (renderers.get(name.toLowerCase()) === renderer) {
      renderers.delete(name.toLowerCase())
    }
  }
}

export function getToolRenderer(name: string): ToolRenderer | undefined {
  return renderers.get(name.toLowerCase())
}

export function clearToolRenderers(): void {
  renderers.clear()
}

export function toToolRenderProps(part: ToolPart): ToolRenderProps {
  return {
    status: part.state.status,
    name: part.tool,
    input: part.state.input,
    output: part.state.output,
    error: part.state.error,
  }
}
