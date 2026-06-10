import { apiClient } from "@/lib/api-client"
import type { AgentEvent, ChatAttachment, ChatContextAttachment } from "@/features/chat/types"
import type { SessionMeta } from "@/stores/chat-store"

export interface ContentPart {
  type: "text" | "image_url" | "file_url"
  text?: string
  image_url?: { url: string }
  file_url?: { url: string; file_name: string }
}

// API request message format (for backend communication)
export interface APIChatMessage {
  role: "user" | "assistant" | "system" | "tool"
  content: string | ContentPart[]
}

// Alias for backward compatibility
export type ChatMessage = APIChatMessage

export interface ModelConfig {
  model_name: string
  base_url: string
  api_key: string
  model_type?: string
  api_version?: string
}

export interface ChatCompleteOptions {
  messages: ChatMessage[]
  model: string
  modelConfig?: ModelConfig
  stream?: boolean
  selectParam?: string
  extInfo?: Record<string, unknown>
  session_id?: string | null
}

// --- Session / Conversation CRUD ---

export interface SessionLoadResponse {
  session: SessionMeta
  messages: {
    id?: string
    type: string
    role?: "user" | "assistant" | "system" | "tool"
    content: string
    timestamp?: number
    end_time?: number
    updated_at?: number
    tool_name?: string
    tool_call_id?: string
    tool_calls?: unknown[]
    events?: AgentEvent[]
    attachments?: ChatAttachment[]
    context_attachments?: ChatContextAttachment[]
    contextAttachments?: ChatContextAttachment[]
  }[]
}

export interface SessionMessageUpsertInput {
  type: "user" | "assistant" | "system" | "tool_use" | "tool_result"
  role?: "user" | "assistant" | "system" | "tool"
  content?: string
  events?: AgentEvent[]
  attachments?: ChatAttachment[]
  context_attachments?: ChatContextAttachment[]
  contextAttachments?: ChatContextAttachment[]
  tool_calls?: unknown[]
  tool_call_id?: string
  tool_name?: string
  timestamp?: number
  end_time?: number
}

export async function createSession(): Promise<{ session_id: string; session: SessionMeta }> {
  const res = await apiClient.post("/v1/chat/sessions")
  return res.data
}

export async function listSessions(): Promise<{ sessions: SessionMeta[] }> {
  const res = await apiClient.get("/v1/chat/sessions")
  return res.data
}

export async function loadSession(sessionId: string): Promise<SessionLoadResponse> {
  const res = await apiClient.get(`/v1/chat/sessions/${sessionId}`)
  return res.data
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/v1/chat/sessions/${sessionId}`)
}

export async function upsertSessionMessage(
  sessionId: string,
  messageId: string,
  input: SessionMessageUpsertInput,
): Promise<SessionLoadResponse> {
  const res = await apiClient.put(
    `/v1/chat/sessions/${sessionId}/messages/${messageId}`,
    input,
  )
  return res.data
}

// --- Chat Completion ---

export async function chatComplete(options: ChatCompleteOptions) {
  const {
    messages,
    model,
    modelConfig,
    stream = false,
    selectParam,
    extInfo,
    session_id,
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
      session_id,
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
