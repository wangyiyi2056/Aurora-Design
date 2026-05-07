import type { APIChatMessage } from "@/services/chat"
import type { ByokConfig } from "@/stores/provider-store"
import { streamProxyEndpoint, type StreamHandlers } from "@/providers/api-proxy"

export async function streamMessageOpenAI(
  cfg: ByokConfig,
  history: APIChatMessage[],
  signal: AbortSignal,
  handlers: StreamHandlers,
): Promise<void> {
  return streamProxyEndpoint("/api/v1/proxy/openai/stream", cfg, history, signal, handlers)
}

export function isOpenAICompatible(model: string, baseUrl: string): boolean {
  const m = model.toLowerCase()
  const u = baseUrl.toLowerCase()
  const parsed = new URL(u || "https://api.anthropic.com", "https://local.invalid")
  const pathSegments = parsed.pathname.split("/").filter(Boolean)
  const isOfficialAnthropic = parsed.hostname === "api.anthropic.com"
  const last = pathSegments.at(-1) ?? ""
  const prev = pathSegments.at(-2) ?? ""
  const isAnthropicEndpoint = last === "anthropic" || (/^v\d+$/.test(last) && prev === "anthropic")

  if (isAnthropicEndpoint) return false
  if (u.includes("xiaomimimo.com/v1")) return true
  if (u.includes("api.minimaxi.com/v1")) return true
  if (u.includes("api.deepseek")) return true
  if (u.includes("api.groq")) return true
  if (u.includes("api.together")) return true
  if (u.includes("openrouter")) return true
  if (u.includes("openai.com")) return true
  if (m.startsWith("deepseek")) return true
  if (m.startsWith("groq") || m.startsWith("llama") || m.startsWith("mixtral")) return true
  if (m.startsWith("gpt-") || m.startsWith("o1") || m.startsWith("o3") || m.startsWith("o4")) return true
  if (m.startsWith("mimo")) return true
  return Boolean(u && !isOfficialAnthropic)
}
