import { useState, useCallback, useRef } from "react"
import type { QueryRequest, QueryReference } from "@/services/knowledge-v2"

interface StreamingQueryState {
  response: string
  references: QueryReference[]
  isStreaming: boolean
  error: string | null
}

interface StreamingQueryResult extends StreamingQueryState {
  execute: (request: QueryRequest) => Promise<void>
  abort: () => void
}

async function getBaseURL(): Promise<string> {
  if (typeof window !== "undefined" && window.electronAPI) {
    return window.electronAPI.getBackendUrl()
  }
  return "/api"
}

export function useStreamingQuery(knowledgeName: string): StreamingQueryResult {
  const [state, setState] = useState<StreamingQueryState>({
    response: "",
    references: [],
    isStreaming: false,
    error: null,
  })

  const abortControllerRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
  }, [])

  const execute = useCallback(
    async (request: QueryRequest) => {
      // Abort any in-flight stream before starting a new one
      abort()

      const controller = new AbortController()
      abortControllerRef.current = controller

      setState({
        response: "",
        references: [],
        isStreaming: true,
        error: null,
      })

      try {
        const baseURL = await getBaseURL()
        const url = `${baseURL}/v1/knowledge/${encodeURIComponent(knowledgeName)}/query/stream`

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...request, stream: true }),
          signal: controller.signal,
        })

        if (!response.ok) {
          const errorBody = await response.text().catch(() => "Unknown error")
          throw new Error(`Query failed (${response.status}): ${errorBody}`)
        }

        if (!response.body) {
          throw new Error("Response body is not available for streaming")
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()

        let accumulatedResponse = ""
        let buffer = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Process complete NDJSON lines
          const lines = buffer.split("\n")
          // Keep the last (potentially incomplete) chunk in the buffer
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            try {
              const parsed = JSON.parse(trimmed) as Record<string, unknown>

              if (Array.isArray(parsed.references)) {
                setState((prev) => ({
                  ...prev,
                  references: parsed.references as QueryReference[],
                }))
              }

              if (typeof parsed.response === "string") {
                accumulatedResponse += parsed.response
                setState((prev) => ({
                  ...prev,
                  response: accumulatedResponse,
                }))
              }

              if (typeof parsed.error === "string") {
                setState((prev) => ({
                  ...prev,
                  error: parsed.error as string,
                }))
              }
            } catch {
              // Skip malformed JSON lines
            }
          }
        }

        // Process any remaining buffer content
        if (buffer.trim()) {
          try {
            const parsed = JSON.parse(buffer.trim()) as Record<string, unknown>
            if (typeof parsed.response === "string") {
              accumulatedResponse += parsed.response
              setState((prev) => ({
                ...prev,
                response: accumulatedResponse,
              }))
            }
          } catch {
            // Ignore trailing partial data
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // Abort is intentional — do not set error state
          return
        }

        const message = err instanceof Error ? err.message : "Streaming query failed"
        setState((prev) => ({
          ...prev,
          error: message,
        }))
      } finally {
        setState((prev) => ({ ...prev, isStreaming: false }))
        abortControllerRef.current = null
      }
    },
    [knowledgeName, abort]
  )

  return {
    ...state,
    execute,
    abort,
  }
}
