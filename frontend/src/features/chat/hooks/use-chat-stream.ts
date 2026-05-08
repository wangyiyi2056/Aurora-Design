import { useMutation } from "@tanstack/react-query"
import { chatComplete, type APIChatMessage, type ModelConfig } from "@/services/chat"
import { streamByokProvider } from "@/providers/registry"
import type { ApiProtocol, ByokConfig } from "@/stores/provider-store"
import { useChatStore } from "@/stores/chat-store"
import { ChatSSEState, parseSSEChunk, extractPipelineSteps } from "@/features/chat/utils/sse-parser"

interface UseChatStreamOptions {
  onSuccess?: (content: string) => void
  onError?: (error: Error) => void
}

interface ChatStreamParams {
  messages: APIChatMessage[]
  model: string
  modelConfig?: ModelConfig
  selectParam?: string
  extInfo?: Record<string, unknown>
  session_id?: string | null
  onDone?: () => void
}

/** Legacy non-streaming mutation for backward compatibility. */
export function useChatStream(options: UseChatStreamOptions = {}) {
  return useMutation({
    mutationFn: async ({ messages, model, modelConfig, selectParam, extInfo, session_id }: ChatStreamParams) => {
      const data = await chatComplete({
        messages,
        model,
        modelConfig,
        stream: false,
        selectParam,
        extInfo,
        session_id,
      })
      const content =
        data.choices?.[0]?.message?.content || JSON.stringify(data)
      return content as string
    },
    onSuccess: options.onSuccess,
    onError: options.onError,
  })
}

/** Default timeout for chat requests (60 seconds) */
const DEFAULT_TIMEOUT_MS = 60000

/**
 * Send a streaming chat request via fetch + SSE.
 * Uses ChatSSEState to parse events and build MessagePart[].
 * Creates an AbortController and stores it in the chat store for cancellation support.
 *
 * @param params - Chat request parameters
 * @param externalAbortSignal - Optional external AbortSignal for cancellation
 * @param timeoutMs - Optional timeout in milliseconds (default 60s)
 * @returns The AbortController used for this request (can be aborted externally)
 */
export function sendChatStream(
  params: ChatStreamParams,
  externalAbortSignal?: AbortSignal,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): AbortController {
  const { setAbortController } = useChatStore.getState()

  const parser = new ChatSSEState()

  // Create AbortController for this request (primary control)
  const abortController = new AbortController()

  // Create separate timeout controller
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs)

  // Combine signals: external + user abort + timeout
  const combinedSignal = AbortSignal.any([
    abortController.signal,
    timeoutController.signal,
    ...(externalAbortSignal ? [externalAbortSignal] : []),
  ])

  // Store the abortController in the store for external cancellation
  setAbortController(abortController)

  // Execute the streaming request
  executeStreamRequest(
    params,
    combinedSignal,
    timeoutId,
    parser,
    abortController,
    timeoutController,
    externalAbortSignal,
    timeoutMs,
  )

  return abortController
}

/**
 * Internal function to execute the streaming request.
 * Separated to allow abortController to be returned immediately.
 */
async function executeStreamRequest(
  params: ChatStreamParams,
  combinedSignal: AbortSignal,
  timeoutId: ReturnType<typeof setTimeout>,
  parser: ChatSSEState,
  abortController: AbortController,
  timeoutController: AbortController,
  externalAbortSignal: AbortSignal | undefined,
  timeoutMs: number,
): Promise<void> {
  const {
    addMessage,
    setMessages,
    setLoading,
    setStreamingParts,
    setStreamingStatus,
    setAbortController,
    updatePipelineStep,
    resetPipelineSteps,
    debugPipelineEnabled,
  } = useChatStore.getState()
  const assistantStartTime = Date.now()
  addMessage({
    role: "assistant",
    content: [],
    startTime: assistantStartTime,
  })

  const updateStreamingAssistant = (endTime?: number) => {
    const parts = parser.toMessageParts()
    const finalContent = parser.getFinalContent()
    const content = parts.length > 0 ? parts : finalContent
    const current = useChatStore.getState().messages
    let updated = false
    const next = current.map((message) => {
      if (
        !updated &&
        message.role === "assistant" &&
        message.startTime === assistantStartTime
      ) {
        updated = true
        return {
          ...message,
          content,
          endTime,
        }
      }
      return message
    })
    if (updated) {
      setMessages(next)
    }
  }

  const removeEmptyStreamingAssistant = () => {
    const parts = parser.toMessageParts()
    const hasVisibleOutput =
      Boolean(parser.getFinalContent()) ||
      parts.some((part) => part.type !== "text" || part.text.trim().length > 0)
    if (hasVisibleOutput) {
      updateStreamingAssistant(Date.now())
      return
    }
    const current = useChatStore.getState().messages
    setMessages(
      current.filter(
        (message) =>
          !(
            message.role === "assistant" &&
            message.startTime === assistantStartTime
          ),
      ),
    )
  }

  // Reset pipeline steps at start of new conversation
  if (debugPipelineEnabled) {
    resetPipelineSteps()
  }

  try {
    const byokConfig = modelConfigToByok(params.modelConfig)
    if (byokConfig) {
      let byokError: Error | null = null
      let byokReasoningActive = false
      parser.processEvent({ type: "text_start" })
      setStreamingParts(parser.toMessageParts())
      setStreamingStatus("Streaming")
      updateStreamingAssistant()

      await streamByokProvider(byokConfig.protocol, byokConfig, params.messages, combinedSignal, {
        onDelta: (delta) => {
          if (byokReasoningActive) {
            parser.processEvent({ type: "reasoning_end" })
            byokReasoningActive = false
          }
          parser.processEvent({ type: "text_delta", content: delta })
          setStreamingParts(parser.toMessageParts())
          setStreamingStatus(parser.getCurrentStatus())
          updateStreamingAssistant()
        },
        onReasoningDelta: (delta) => {
          if (!byokReasoningActive) {
            parser.processEvent({ type: "reasoning_start" })
            byokReasoningActive = true
          }
          parser.processEvent({ type: "reasoning_delta", content: delta })
          setStreamingParts(parser.toMessageParts())
          setStreamingStatus(parser.getCurrentStatus())
          updateStreamingAssistant()
        },
        onDone: () => {
          if (byokReasoningActive) {
            parser.processEvent({ type: "reasoning_end" })
            byokReasoningActive = false
          }
          parser.processEvent({ type: "text_end", model: byokConfig.model })
          updateStreamingAssistant(parser.getEndTime() ?? Date.now())
        },
        onError: (error) => {
          byokError = error
        },
      })
      if (byokError) throw byokError

      params.onDone?.()
      return
    }

    const resp = await fetch("/api/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: params.messages,
        model: params.model,
        stream: true,
        model_config: params.modelConfig,
        select_param: params.selectParam,
        ext_info: params.extInfo,
        session_id: params.session_id,
      }),
      signal: combinedSignal,
    })

    if (!resp.ok) {
      const errText = await resp.text()
      let detail = errText
      try {
        const parsed = JSON.parse(errText)
        detail = parsed.detail || parsed.message || errText
      } catch {
        // Not JSON — likely HTML error page, use status-based message
        if (errText.trim().startsWith("<!DOCTYPE") || errText.trim().startsWith("<html")) {
          detail = `Server error (status ${resp.status})`
        } else {
          detail = errText.slice(0, 300)
        }
      }
      throw new Error(detail)
    }

    const reader = resp.body?.getReader()
    if (!reader) throw new Error("No response body")

    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith("data:")) continue

        const events = parseSSEChunk(trimmed)
        for (const event of events) {
          parser.processEvent(event)

          // Update streaming state for real-time UI updates
          setStreamingParts(parser.toMessageParts())
          setStreamingStatus(parser.getCurrentStatus())
          updateStreamingAssistant(parser.getEndTime())

          // Handle pipeline step events for debug panel
          if (debugPipelineEnabled && event.type === "pipeline_step") {
            const pipelineSteps = extractPipelineSteps([event])
            for (const step of pipelineSteps) {
              updatePipelineStep(step)
            }
          }
        }
      }
    }

    updateStreamingAssistant(parser.getEndTime() ?? Date.now())
    params.onDone?.()

  } catch (error) {
    // Handle different error types with appropriate messages
    let errorMessage: string
    if (error instanceof Error) {
      if (error.name === "AbortError") {
        // Check which signal triggered the abort
        if (abortController.signal.aborted) {
          errorMessage = "Request was cancelled"
        } else if (timeoutController.signal.aborted) {
          errorMessage = `Request timed out after ${timeoutMs / 1000}s`
        } else if (externalAbortSignal?.aborted) {
          errorMessage = "Request was cancelled"
        } else {
          errorMessage = "Request was cancelled"
        }
      } else {
        errorMessage = error.message
      }
    } else {
      errorMessage = "Unknown error"
    }

    removeEmptyStreamingAssistant()
    // Add error as system message (not assistant) for clear distinction
    addMessage({
      role: "system",
      content: `⚠️ ${errorMessage}`,
    })
  } finally {
    // Clean up timeout
    clearTimeout(timeoutId)
    setLoading(false)
    setStreamingParts([])
    setStreamingStatus(null)
    setAbortController(null)
  }
}

function modelConfigToByok(modelConfig?: ModelConfig): ByokConfig | null {
  const protocol = modelConfig?.model_type
  if (!isApiProtocol(protocol)) return null
  return {
    protocol,
    baseUrl: modelConfig?.base_url ?? "",
    apiKey: modelConfig?.api_key ?? "",
    model: modelConfig?.model_name ?? "",
    apiVersion: modelConfig?.api_version ?? "",
  }
}

function isApiProtocol(value: unknown): value is ApiProtocol {
  return value === "openai" || value === "anthropic" || value === "azure" || value === "google"
}
