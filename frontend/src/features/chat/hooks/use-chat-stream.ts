import { useMutation } from "@tanstack/react-query"
import { chatComplete, type ChatMessage, type ModelConfig } from "@/services/chat"
import { useChatStore } from "@/stores/chat-store"

interface UseChatStreamOptions {
  onSuccess?: (content: string) => void
  onError?: (error: Error) => void
}

interface ChatStreamParams {
  messages: ChatMessage[]
  model: string
  modelConfig: ModelConfig
  selectParam?: string
  extInfo?: Record<string, unknown>
}

/** Legacy non-streaming mutation for backward compatibility. */
export function useChatStream(options: UseChatStreamOptions = {}) {
  return useMutation({
    mutationFn: async ({ messages, model, modelConfig, selectParam, extInfo }: ChatStreamParams) => {
      const data = await chatComplete({
        messages,
        model,
        modelConfig,
        stream: false,
        selectParam,
        extInfo,
      })
      const content =
        data.choices?.[0]?.message?.content || JSON.stringify(data)
      return content as string
    },
    onSuccess: options.onSuccess,
    onError: options.onError,
  })
}

interface SSEEvent {
  type: "text_start" | "text_delta" | "text_end" | "tool_call_start" | "tool_call_result"
  content?: string
  tool_name?: string
  arguments?: string
  finish_reason?: string
  id?: string
  model?: string
  usage?: Record<string, unknown>
}

/**
 * Send a streaming chat request via fetch + SSE.
 * The caller manages loading state and stores the response via addMessage/appendToLastMessage.
 */
export async function sendChatStream(
  params: ChatStreamParams
): Promise<void> {
  const { appendToLastMessage, addMessage, setLoading } = useChatStore.getState()

  try {
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
      }),
    })

    if (!resp.ok) {
      const errText = await resp.text()
      throw new Error(`Chat API error ${resp.status}: ${errText}`)
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

        const dataStr = trimmed.slice(5).trim()
        if (dataStr === "[DONE]") continue

        try {
          const event: SSEEvent = JSON.parse(dataStr)

          switch (event.type) {
            case "text_start":
              break

            case "text_delta":
              if (event.content) {
                appendToLastMessage(event.content)
              }
              break

            case "text_end":
              break

            case "tool_call_start":
              if (event.tool_name) {
                addMessage({
                  role: "system",
                  content: `🔧 Calling: ${event.tool_name}`,
                })
              }
              break

            case "tool_call_result":
              if (event.tool_name && event.content) {
                const preview =
                  event.content.length > 200
                    ? event.content.slice(0, 200) + "..."
                    : event.content
                addMessage({
                  role: "system",
                  content: `✅ ${event.tool_name}: ${preview}`,
                })
              }
              break
          }
        } catch {
          // Skip unparseable lines
        }
      }
    }
  } catch (error) {
    addMessage({
      role: "assistant",
      content: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
    })
  } finally {
    setLoading(false)
  }
}
