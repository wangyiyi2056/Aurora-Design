import type { ApiProtocol, ByokConfig } from "@/stores/provider-store"

export const CUSTOM_MODEL_SENTINEL = "__custom__"

export interface KnownProvider {
  label: string
  protocol: ApiProtocol
  baseUrl: string
  model: string
  models?: string[]
}

export const PROVIDER_DEFAULTS: Record<ApiProtocol, ByokConfig & { placeholder: string }> = {
  anthropic: {
    protocol: "anthropic",
    baseUrl: "https://api.anthropic.com",
    apiKey: "",
    model: "claude-sonnet-4-5",
    apiVersion: "",
    placeholder: "sk-ant-...",
  },
  openai: {
    protocol: "openai",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
    model: "gpt-4o",
    apiVersion: "",
    placeholder: "sk-...",
  },
  azure: {
    protocol: "azure",
    baseUrl: "",
    apiKey: "",
    model: "",
    apiVersion: "2024-10-21",
    placeholder: "azure key",
  },
  google: {
    protocol: "google",
    baseUrl: "https://generativelanguage.googleapis.com",
    apiKey: "",
    model: "gemini-2.0-flash",
    apiVersion: "",
    placeholder: "AIza...",
  },
}

export const KNOWN_PROVIDERS: KnownProvider[] = [
  {
    label: "Anthropic (Claude)",
    protocol: "anthropic",
    baseUrl: "https://api.anthropic.com",
    model: "claude-sonnet-4-5",
    models: ["claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"],
  },
  {
    label: "DeepSeek - Anthropic",
    protocol: "anthropic",
    baseUrl: "https://api.deepseek.com/anthropic",
    model: "deepseek-chat",
    models: ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro"],
  },
  {
    label: "MiniMax - Anthropic",
    protocol: "anthropic",
    baseUrl: "https://api.minimaxi.com/anthropic",
    model: "MiniMax-M2.7-highspeed",
    models: [
      "MiniMax-M2.7-highspeed",
      "MiniMax-M2.7",
      "MiniMax-M2.5-highspeed",
      "MiniMax-M2.5",
      "MiniMax-M2.1-highspeed",
      "MiniMax-M2.1",
      "MiniMax-M2",
    ],
  },
  {
    label: "OpenAI",
    protocol: "openai",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o",
    models: ["gpt-4o", "gpt-4o-mini", "o3", "o4-mini"],
  },
  {
    label: "Azure OpenAI",
    protocol: "azure",
    baseUrl: "",
    model: "",
    models: [],
  },
  {
    label: "Google Gemini",
    protocol: "google",
    baseUrl: "https://generativelanguage.googleapis.com",
    model: "gemini-2.0-flash",
    models: ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
  },
  {
    label: "DeepSeek - OpenAI",
    protocol: "openai",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-chat",
    models: ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro"],
  },
  {
    label: "MiniMax - OpenAI",
    protocol: "openai",
    baseUrl: "https://api.minimaxi.com/v1",
    model: "MiniMax-M2.7-highspeed",
    models: [
      "MiniMax-M2.7-highspeed",
      "MiniMax-M2.7",
      "MiniMax-M2.5-highspeed",
      "MiniMax-M2.5",
      "MiniMax-M2.1-highspeed",
      "MiniMax-M2.1",
      "MiniMax-M2",
    ],
  },
  {
    label: "MiMo (Xiaomi) - OpenAI",
    protocol: "openai",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
    model: "mimo-v2.5-pro",
    models: ["mimo-v2.5-pro"],
  },
  {
    label: "MiMo (Xiaomi) - Anthropic",
    protocol: "anthropic",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/anthropic",
    model: "mimo-v2.5-pro",
    models: ["mimo-v2.5-pro"],
  },
]

export const SUGGESTED_MODELS_BY_PROTOCOL: Record<ApiProtocol, string[]> = {
  anthropic: [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.7",
    "MiniMax-M2.5-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.1-highspeed",
    "MiniMax-M2.1",
    "MiniMax-M2",
    "mimo-v2.5-pro",
  ],
  openai: [
    "gpt-4o",
    "gpt-4o-mini",
    "o3",
    "o4-mini",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.7",
    "MiniMax-M2.5-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.1-highspeed",
    "MiniMax-M2.1",
    "MiniMax-M2",
    "mimo-v2.5-pro",
  ],
  azure: ["gpt-4o", "gpt-4o-mini"],
  google: ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
}

export function defaultByokConfig(protocol: ApiProtocol): ByokConfig {
  const { placeholder: _placeholder, ...config } = PROVIDER_DEFAULTS[protocol]
  return { ...config }
}

export function isValidApiBaseUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === "http:" || url.protocol === "https:"
  } catch {
    return false
  }
}
