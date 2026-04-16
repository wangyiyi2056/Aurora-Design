import { useMutation } from "@tanstack/react-query"
import { chatComplete, type ChatMessage, type ModelConfig } from "@/services/chat"

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
