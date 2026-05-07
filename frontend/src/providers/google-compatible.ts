import type { APIChatMessage } from "@/services/chat"
import type { ByokConfig } from "@/stores/provider-store"
import { streamProxyEndpoint, type StreamHandlers } from "@/providers/api-proxy"

export async function streamMessageGoogle(
  cfg: ByokConfig,
  history: APIChatMessage[],
  signal: AbortSignal,
  handlers: StreamHandlers,
): Promise<void> {
  return streamProxyEndpoint("/api/v1/proxy/google/stream", cfg, history, signal, handlers)
}
