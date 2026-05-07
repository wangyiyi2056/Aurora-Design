import type { APIChatMessage } from "@/services/chat"
import type { ApiProtocol, ByokConfig } from "@/stores/provider-store"
import { streamMessageAnthropicProxy } from "@/providers/anthropic-compatible"
import { streamMessageAzure } from "@/providers/azure-compatible"
import { streamMessageGoogle } from "@/providers/google-compatible"
import { streamMessageOpenAI } from "@/providers/openai-compatible"
import type { StreamHandlers } from "@/providers/api-proxy"

export function streamByokProvider(
  protocol: ApiProtocol,
  cfg: ByokConfig,
  history: APIChatMessage[],
  signal: AbortSignal,
  handlers: StreamHandlers,
): Promise<void> {
  if (protocol === "anthropic") return streamMessageAnthropicProxy(cfg, history, signal, handlers)
  if (protocol === "azure") return streamMessageAzure(cfg, history, signal, handlers)
  if (protocol === "google") return streamMessageGoogle(cfg, history, signal, handlers)
  return streamMessageOpenAI(cfg, history, signal, handlers)
}
