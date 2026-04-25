import { apiClient } from "@/lib/api-client"

export interface ContentPart {
  type: "text" | "image_url" | "file_url"
  text?: string
  image_url?: { url: string }
  file_url?: { url: string; file_name: string }
}

export interface ChatMessage {
  role: "user" | "assistant" | "system" | "tool"
  content: string | ContentPart[]
}

export interface ModelConfig {
  model_name: string
  base_url: string
  api_key: string
  model_type?: string
}

export interface ChatCompleteOptions {
  messages: ChatMessage[]
  model: string
  modelConfig: ModelConfig
  stream?: boolean
  selectParam?: string
  extInfo?: Record<string, unknown>
}

export async function chatComplete(options: ChatCompleteOptions) {
  const {
    messages,
    model,
    modelConfig,
    stream = false,
    selectParam,
    extInfo,
  } = options

  const res = await apiClient.post(
    "/v1/chat/completions",
    {
      messages,
      model,
      stream,
      model_config: modelConfig,
      select_param: selectParam,
      ext_info: extInfo,
    },
    {
      timeout: 60000,
      headers: {
        "Content-Type": "application/json",
      },
      responseType: stream ? "text" : "json",
    }
  )

  if (stream) return res.request.response
  return res.data
}
