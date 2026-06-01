import { useState, useEffect, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  Cpu,
  Eye,
  EyeOff,
  KeyRound,
  RefreshCw,
  Terminal,
  Box,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  listAgents,
  testEmbeddingConnection,
  createModelConfig,
  updateModelConfig,
  deleteModelConfig,
  listModelConfigs,
} from "@/services/models"
import {
  CUSTOM_MODEL_SENTINEL,
  KNOWN_PROVIDERS,
  PROVIDER_DEFAULTS,
  SUGGESTED_MODELS_BY_PROTOCOL,
  isValidApiBaseUrl,
} from "@/state/config"
import { useChatStore } from "@/stores/chat-store"
import { type ApiProtocol, useProviderStore } from "@/stores/provider-store"
import { cn } from "@/lib/utils"

const protocolTabs: { value: ApiProtocol; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "azure", label: "Azure" },
  { value: "google", label: "Google" },
]

export default function ModelsPage() {
  const [showApiKey, setShowApiKey] = useState(false)
  const qc = useQueryClient()

  const mode = useProviderStore((s) => s.mode)
  const byok = useProviderStore((s) => s.byok)
  const selectedAgentId = useProviderStore((s) => s.selectedAgentId)
  const agentModels = useProviderStore((s) => s.agentModels)
  const embeddingConfig = useProviderStore((s) => s.embeddingConfig)
  const embeddingSavedId = useProviderStore((s) => s.embeddingSavedId)
  const embeddingTested = useProviderStore((s) => s.embeddingTested)
  const chatSavedId = useProviderStore((s) => s.chatSavedId)
  const chatSavedType = useProviderStore((s) => s.chatSavedType)
  const setMode = useProviderStore((s) => s.setMode)
  const setByok = useProviderStore((s) => s.setByok)
  const setApiProtocol = useProviderStore((s) => s.setApiProtocol)
  const setSelectedAgentId = useProviderStore((s) => s.setSelectedAgentId)
  const setAgentModelChoice = useProviderStore((s) => s.setAgentModelChoice)
  const setEmbeddingConfig = useProviderStore((s) => s.setEmbeddingConfig)
  const setEmbeddingSavedId = useProviderStore((s) => s.setEmbeddingSavedId)
  const setEmbeddingTested = useProviderStore((s) => s.setEmbeddingTested)
  const setChatSaved = useProviderStore((s) => s.setChatSaved)
  const setChatModel = useChatStore((s) => s.setModel)

  // ── Agent queries ──────────────────────────────────────────────────
  const agentsQuery = useQuery({
    queryKey: ["agents", "list"],
    queryFn: listAgents,
    staleTime: 10_000,
  })

  // ── Load existing embedding config from backend on mount ───────────
  const { data: modelConfigs } = useQuery({
    queryKey: ["models", "configs"],
    queryFn: listModelConfigs,
    staleTime: 30_000,
  })

  // Sync embeddingSavedId + form fields from backend if browser lost them
  useEffect(() => {
    const savedEmbedding = modelConfigs?.items.find((m) => m.type === "embedding")
    if (savedEmbedding && !embeddingSavedId) {
      setEmbeddingSavedId(savedEmbedding.id)
      // Extract host from base_url: "http://localhost:11434/v1" → "http://localhost:11434"
      const host = savedEmbedding.base_url.replace(/\/v1\/?$/, "")
      // Extract model from name: "ollama-nomic-embed-text" → "nomic-embed-text"
      const model = savedEmbedding.name.replace(/^ollama-/, "")
      setEmbeddingConfig({ host, model })
    }
  }, [modelConfigs, embeddingSavedId, setEmbeddingSavedId, setEmbeddingConfig])

  const agents = agentsQuery.data?.agents || []
  const availableAgents = agents.filter((agent) => agent.available)
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId)
  const selectedChoice = selectedAgentId ? agentModels[selectedAgentId] ?? {} : {}

  // ── Backend readiness (for tab dots) ────────────────────────────
  const { data: readiness } = useQuery({
    queryKey: ["models", "readiness"],
    queryFn: () => import("@/services/models").then((m) => m.getModelReadiness()),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })

  // ── Sync chat config from backend on mount ──────────────────────
  const chatSyncedRef = useRef(false)
  useEffect(() => {
    if (chatSyncedRef.current) return
    const savedChat = modelConfigs?.items.find((m) => m.type === "llm" || m.type === "anthropic" || m.type === "daemon")
    if (savedChat && !chatSavedId) {
      const inferredType = savedChat.type === "daemon" ? "daemon" : "api"
      setChatSaved(savedChat.id, inferredType)
      chatSyncedRef.current = true
    }
  }, [modelConfigs, chatSavedId, setChatSaved])

  // ── Tab status dots ──────────────────────────────────────────────
  // 本机 CLI: backend has LLM AND the saved config is a daemon type
  const daemonReady = Boolean(
    readiness?.llm && chatSavedType === "daemon" && selectedAgentId
  )
  // BYOK API: backend has LLM AND the saved config is an API type
  const byokReady = Boolean(
    readiness?.llm && chatSavedType === "api"
  )
  // Embedding: connection test passed (Ollama is local, backend can't always detect)
  const embeddingReady = embeddingTested

  const chooseAgent = (agentId: string) => {
    setSelectedAgentId(agentId)
    setMode("daemon")
    setChatModel(agentId)

    // Auto-save CLI agent to backend so the V2 knowledge pipeline can use it
    saveChatConfig.mutate({
      name: `chat-cli-${agentId}`,
      type: "daemon",
      base_url: agentId,
      api_key: "",
      chatType: "daemon",
    })
  }

  const refreshAgents = async () => {
    try {
      const result = await agentsQuery.refetch()
      const count = result.data?.agents.filter((agent) => agent.available).length ?? 0
      toast.success(`已扫描到 ${count} 个本机 CLI`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "扫描本机 CLI 失败")
    }
  }

  const switchProtocol = (protocol: ApiProtocol) => {
    setApiProtocol(protocol)
  }

  // ── Embedding mutations ────────────────────────────────────────────
  const testEmbedding = useMutation({
    mutationFn: () => testEmbeddingConnection(embeddingConfig.host, embeddingConfig.model),
    onSuccess: (data) => {
      if (data.success) {
        const dim = data.model_info?.dimension ?? embeddingConfig.dim
        if (dim && dim !== embeddingConfig.dim) {
          setEmbeddingConfig({ dim })
        }
        setEmbeddingTested(true)
        toast.success(`连接成功 — 维度 ${dim}`)
      } else {
        setEmbeddingTested(false)
        toast.error(data.message || "连接失败")
      }
    },
    onError: (err: unknown) => {
      setEmbeddingTested(false)
      toast.error(err instanceof Error ? err.message : "连接失败")
    },
  })

  const saveEmbedding = useMutation({
    mutationFn: async () => {
      // Ollama uses OpenAI-compatible endpoint at {host}/v1
      const openaiBaseUrl = `${embeddingConfig.host.replace(/\/$/, "")}/v1`

      if (embeddingSavedId) {
        return updateModelConfig(embeddingSavedId, {
          name: `ollama-${embeddingConfig.model}`,
          type: "embedding",
          base_url: openaiBaseUrl,
          api_key: "ollama",
        })
      }

      // Check if we need to delete the old one first (name conflict)
      try {
        return await createModelConfig({
          name: `ollama-${embeddingConfig.model}`,
          type: "embedding",
          base_url: openaiBaseUrl,
          api_key: "ollama",
          is_default: true,
        })
      } catch (err: unknown) {
        // If name conflict (409), try to update existing
        if (err && typeof err === "object" && "response" in err) {
          const response = (err as { response?: { status?: number } }).response
          if (response?.status === 409) {
            toast.error("该 Embedding 模型已存在，请先删除旧配置")
            throw err
          }
        }
        throw err
      }
    },
    onSuccess: (data) => {
      setEmbeddingSavedId(data.id)
      toast.success("Embedding 模型已保存并注册")
      qc.invalidateQueries({ queryKey: ["models", "readiness"] })
      qc.invalidateQueries({ queryKey: ["models", "configs"] })
    },
    onError: (err: unknown) => {
      if (err instanceof Error) {
        toast.error(err.message)
      }
    },
  })

  const removeEmbedding = useMutation({
    mutationFn: async () => {
      if (!embeddingSavedId) return
      await deleteModelConfig(embeddingSavedId)
    },
    onSuccess: () => {
      setEmbeddingSavedId(null)
      toast.success("Embedding 模型已删除")
      qc.invalidateQueries({ queryKey: ["models", "readiness"] })
      qc.invalidateQueries({ queryKey: ["models", "configs"] })
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "删除失败")
      setEmbeddingSavedId(null)
    },
  })

  // ── Chat config save (auto-save to backend) ──────────────────────
  const saveChatConfig = useMutation({
    mutationFn: async (data: {
      name: string
      type: string
      base_url: string
      api_key: string
      chatType: "daemon" | "api"
    }) => {
      // Look up existing record by name (handles race condition where
      // chatSavedId is null but the record already exists in the DB)
      const configs = qc.getQueryData<{ items: { id: string; name: string }[] }>([
        "models",
        "configs",
      ])
      const existingByName = configs?.items.find((m) => m.name === data.name)

      if (existingByName) {
        // Update in-place — avoids unique constraint violation
        const result = await updateModelConfig(existingByName.id, {
          type: data.type,
          base_url: data.base_url,
          api_key: data.api_key,
          is_default: true,
        })
        // If there was a *different* old config, delete it
        if (chatSavedId && chatSavedId !== existingByName.id) {
          await deleteModelConfig(chatSavedId).catch(() => {})
        }
        return { ...result, chatType: data.chatType }
      }

      // No existing record with this name — delete old config then create
      if (chatSavedId) {
        await deleteModelConfig(chatSavedId).catch(() => {})
      }
      const result = await createModelConfig({
        name: data.name,
        type: data.type,
        base_url: data.base_url,
        api_key: data.api_key,
        is_default: true,
      })
      return { ...result, chatType: data.chatType }
    },
    onSuccess: (data) => {
      setChatSaved(data.id, data.chatType)
      qc.invalidateQueries({ queryKey: ["models", "readiness"] })
      qc.invalidateQueries({ queryKey: ["models", "configs"] })
    },
    onError: (err: unknown) => {
      if (err instanceof Error) {
        toast.error(`Chat model save failed: ${err.message}`)
      }
    },
  })

  // ── Debounced BYOK auto-save ────────────────────────────────────
  const byokTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedByokRef = useRef<string>("")
  const byokReadyToSave = Boolean(byok.baseUrl && byok.apiKey && byok.model)
  useEffect(() => {
    if (!byokReadyToSave) return
    if (saveChatConfig.isPending) return

    // Skip if this exact config was already saved
    const configKey = `${byok.protocol}|${byok.baseUrl}|${byok.apiKey}|${byok.model}`
    if (chatSavedType === "api" && configKey === lastSavedByokRef.current) return

    if (byokTimerRef.current) clearTimeout(byokTimerRef.current)
    byokTimerRef.current = setTimeout(() => {
      saveChatConfig.mutate({
        name: `chat-byok-${byok.protocol}`,
        type: byok.protocol,
        base_url: byok.baseUrl,
        api_key: byok.apiKey,
        chatType: "api",
      })
      lastSavedByokRef.current = configKey
    }, 1500)

    return () => {
      if (byokTimerRef.current) clearTimeout(byokTimerRef.current)
    }
  }, [byok.baseUrl, byok.apiKey, byok.model, byok.protocol, byokReadyToSave, chatSavedType, saveChatConfig.isPending])

  // ── Derived state ──────────────────────────────────────────────────
  const modelOptions = selectedAgent?.models?.length ? selectedAgent.models : []
  const modelValue = selectedChoice.model ?? modelOptions[0]?.id ?? "default"
  const isCustomModel =
    selectedChoice.model === "" ||
    (Boolean(selectedChoice.model) &&
      selectedChoice.model !== "default" &&
      !modelOptions.some((model) => model.id === selectedChoice.model))
  const protocolProviders = KNOWN_PROVIDERS.filter((provider) => provider.protocol === byok.protocol)
  const selectedProviderIndex = protocolProviders.findIndex((provider) => provider.baseUrl === byok.baseUrl)
  const selectedProvider = selectedProviderIndex >= 0 ? protocolProviders[selectedProviderIndex] : null
  const apiModelOptions = selectedProvider?.models?.length
    ? selectedProvider.models
    : SUGGESTED_MODELS_BY_PROTOCOL[byok.protocol]
  const apiModelIsCustom = Boolean(byok.model) && !apiModelOptions.includes(byok.model)
  const apiModelSelectValue = apiModelIsCustom || !byok.model ? CUSTOM_MODEL_SENTINEL : byok.model
  const baseUrlInvalid = Boolean(byok.baseUrl) && !isValidApiBaseUrl(byok.baseUrl)

  return (
    <ConstructShell>
      <div className="mb-5">
        <h3 className="m-0 text-base font-semibold">模型 Provider</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          在本机 CLI、BYOK API 和 Embedding 之间切换。CLI 使用本机登录态，BYOK 使用你自己的 API key，Embedding 用于知识库向量化。
        </p>
      </div>

      {/* ── Tab switcher ────────────────────────────────────────────────── */}
      <div className="mb-5 grid grid-cols-3 rounded-lg border border-border bg-muted/40 p-1">
        <button
          type="button"
          onClick={() => setMode("daemon")}
          className={cn(
            "flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "daemon" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          )}
        >
          <span className={cn("h-2 w-2 rounded-full shrink-0 ring-1 ring-inset ring-black/5", daemonReady ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600")} />
          本机 CLI
        </button>
        <button
          type="button"
          onClick={() => setMode("api")}
          className={cn(
            "flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "api" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          )}
        >
          <span className={cn("h-2 w-2 rounded-full shrink-0 ring-1 ring-inset ring-black/5", byokReady ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600")} />
          BYOK API
        </button>
        <button
          type="button"
          onClick={() => setMode("embedding")}
          className={cn(
            "flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "embedding" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          )}
        >
          <span className={cn("h-2 w-2 rounded-full shrink-0 ring-1 ring-inset ring-black/5", embeddingReady ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600")} />
          Embedding
        </button>
      </div>

      {/* ── Daemon (Local CLI) tab ──────────────────────────────────────── */}
      {mode === "daemon" ? (
        <>
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h4 className="m-0 text-sm font-semibold">本机 CLI</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                选择已安装的 Claude Code 或 Codex CLI。选中后自动注册到后端，用于聊天和知识库管线。
              </p>
            </div>
            <Button variant="outline" onClick={refreshAgents} disabled={agentsQuery.isFetching}>
              <RefreshCw className={cn("h-4 w-4 mr-2", agentsQuery.isFetching && "animate-spin")} />
              重新扫描
            </Button>
          </div>

          {agents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-sm text-muted-foreground">
              暂未检测到本机 CLI。请确认后端已重启并安装了 Claude Code 或 Codex CLI。
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {agents.map((agent) => {
                const active = selectedAgentId === agent.id
                return (
                  <button
                    key={agent.id}
                    type="button"
                    disabled={!agent.available}
                    onClick={() => agent.available && chooseAgent(agent.id)}
                    className={cn(
                      "flex min-h-[92px] items-center gap-3 rounded-lg border border-border bg-surface p-4 text-left transition-colors",
                      agent.available && "hover:border-primary/50 hover:bg-surface-hover",
                      active && "border-primary bg-primary/5",
                      !agent.available && "cursor-not-allowed opacity-55"
                    )}
                  >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                      <Terminal className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="font-medium text-text">{agent.name}</span>
                        {active && <Check className="h-4 w-4 text-primary" />}
                      </span>
                      <span className="mt-1 block truncate text-xs text-muted-foreground" title={agent.path || ""}>
                        {agent.available ? agent.version || agent.path || "已安装" : "未安装"}
                      </span>
                    </span>
                    <Badge variant={agent.available ? "default" : "secondary"}>
                      {agent.available ? "可用" : "不可用"}
                    </Badge>
                  </button>
                )
              })}
            </div>
          )}

          {selectedAgent && selectedAgent.available ? (
            <section className="mt-5 rounded-lg border border-border p-4">
              <div className="mb-4 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <h4 className="m-0 text-sm font-semibold">{selectedAgent.name} 运行选项</h4>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {modelOptions.length > 0 ? (
                  <label className="space-y-2">
                    <span className="text-sm font-medium">模型</span>
                    <Select
                      value={isCustomModel ? CUSTOM_MODEL_SENTINEL : modelValue}
                      onValueChange={(value) => {
                        setAgentModelChoice(selectedAgent.id, {
                          model: value === CUSTOM_MODEL_SENTINEL ? "" : value,
                        })
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {modelOptions.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.label}
                          </SelectItem>
                        ))}
                        <SelectItem value={CUSTOM_MODEL_SENTINEL}>自定义...</SelectItem>
                      </SelectContent>
                    </Select>
                  </label>
                ) : null}

                {selectedAgent.reasoningOptions?.length ? (
                  <label className="space-y-2">
                    <span className="text-sm font-medium">推理强度</span>
                    <Select
                      value={selectedChoice.reasoning || selectedAgent.reasoningOptions[0]?.id || "default"}
                      onValueChange={(value) => setAgentModelChoice(selectedAgent.id, { reasoning: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {selectedAgent.reasoningOptions.map((option) => (
                          <SelectItem key={option.id} value={option.id}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </label>
                ) : null}

                {isCustomModel ? (
                  <label className="space-y-2 sm:col-span-2">
                    <span className="text-sm font-medium">自定义模型 ID</span>
                    <Input
                      value={selectedChoice.model || ""}
                      placeholder="输入 CLI 支持的模型 ID"
                      onChange={(event) =>
                        setAgentModelChoice(selectedAgent.id, { model: event.target.value.trim() })
                      }
                    />
                  </label>
                ) : null}
              </div>
            </section>
          ) : availableAgents.length > 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">请选择一个可用 CLI 作为聊天模型。</p>
          ) : null}
        </>
      ) : mode === "api" ? (
        /* ── BYOK API tab ─────────────────────────────────────────────────── */
        <section className="rounded-lg border border-border p-4">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-muted-foreground" />
            <h4 className="m-0 text-sm font-semibold">BYOK API</h4>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {protocolTabs.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => switchProtocol(tab.value)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm transition-colors",
                  byok.protocol === tab.value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 sm:col-span-2">
              <span className="text-sm font-medium">预设 Provider</span>
              <Select
                value={selectedProviderIndex >= 0 ? String(selectedProviderIndex) : "custom"}
                onValueChange={(value) => {
                  if (value === "custom") {
                    setByok({ baseUrl: "", model: "" })
                    return
                  }
                  const provider = protocolProviders[Number(value)]
                  if (!provider) return
                  setByok({
                    baseUrl: provider.baseUrl,
                    model: provider.model,
                  })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="custom">Custom provider</SelectItem>
                  {protocolProviders.map((provider, index) => (
                    <SelectItem key={provider.label} value={String(index)}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="space-y-2 sm:col-span-2">
              <span className="text-sm font-medium">Base URL</span>
              <Input
                value={byok.baseUrl}
                placeholder={PROVIDER_DEFAULTS[byok.protocol].baseUrl}
                onChange={(event) => setByok({ baseUrl: event.target.value.trim() })}
                className={cn(baseUrlInvalid && "border-destructive focus-visible:ring-destructive")}
              />
              {baseUrlInvalid ? <span className="text-xs text-destructive">请输入有效的 http(s) URL</span> : null}
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium">API Key</span>
              <div className="flex gap-2">
                <Input
                  type={showApiKey ? "text" : "password"}
                  value={byok.apiKey}
                  placeholder={PROVIDER_DEFAULTS[byok.protocol].placeholder}
                  onChange={(event) => setByok({ apiKey: event.target.value.trim() })}
                />
                <Button type="button" variant="outline" size="icon" onClick={() => setShowApiKey((value) => !value)}>
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium">{byok.protocol === "azure" ? "Deployment" : "Model"}</span>
              <Select
                value={apiModelSelectValue}
                onValueChange={(value) => setByok({ model: value === CUSTOM_MODEL_SENTINEL ? "" : value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {apiModelOptions.map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                  <SelectItem value={CUSTOM_MODEL_SENTINEL}>自定义...</SelectItem>
                </SelectContent>
              </Select>
            </label>
            {(apiModelIsCustom || apiModelSelectValue === CUSTOM_MODEL_SENTINEL) ? (
              <label className="space-y-2 sm:col-span-2">
                <span className="text-sm font-medium">自定义模型 ID</span>
                <Input
                  value={byok.model}
                  placeholder="输入 provider 支持的模型 ID"
                  onChange={(event) => setByok({ model: event.target.value.trim() })}
                />
              </label>
            ) : null}
            {byok.protocol === "azure" ? (
              <label className="space-y-2">
                <span className="text-sm font-medium">API Version</span>
                <Input
                  value={byok.apiVersion || ""}
                  placeholder="2024-10-21"
                  onChange={(event) => setByok({ apiVersion: event.target.value.trim() })}
                />
              </label>
            ) : null}
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            配置完成后自动保存到后端，知识库管线将使用此模型进行实体抽取。API key 同时保存在浏览器本地用于聊天请求。
          </p>
        </section>
      ) : (
        /* ── Embedding tab ────────────────────────────────────────────────── */
        <section className="rounded-lg border border-border p-4">
          <div className="mb-4 flex items-center gap-2">
            <Box className="h-4 w-4 text-muted-foreground" />
            <h4 className="m-0 text-sm font-semibold">Embedding 模型</h4>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            配置 Embedding 模型用于知识库文档向量化和语义检索。当前支持本地 Ollama。
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Binding type */}
            <label className="space-y-2">
              <span className="text-sm font-medium">Binding</span>
              <Select value={embeddingConfig.binding} disabled>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ollama">Ollama</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">目前仅支持 Ollama</p>
            </label>

            {/* Dimension */}
            <label className="space-y-2">
              <span className="text-sm font-medium">维度 (Dimension)</span>
              <Input
                value={embeddingConfig.dim}
                disabled
                className="bg-muted/50"
              />
              <p className="text-xs text-muted-foreground">由模型自动决定</p>
            </label>

            {/* Host */}
            <label className="space-y-2 sm:col-span-2">
              <span className="text-sm font-medium">Ollama Host</span>
              <Input
                value={embeddingConfig.host}
                placeholder="http://localhost:11434"
                onChange={(event) => {
                  setEmbeddingConfig({ host: event.target.value.trim() })
                  setEmbeddingTested(false)
                }}
              />
              <p className="text-xs text-muted-foreground">
                Ollama 服务地址，默认 http://localhost:11434
              </p>
            </label>

            {/* Model */}
            <label className="space-y-2 sm:col-span-2">
              <span className="text-sm font-medium">Model</span>
              <Select
                value={
                  ["nomic-embed-text", "mxbai-embed-large", "all-minilm", "snowflake-arctic-embed"].includes(embeddingConfig.model)
                    ? embeddingConfig.model
                    : CUSTOM_MODEL_SENTINEL
                }
                onValueChange={(value) => {
                  setEmbeddingConfig({ model: value === CUSTOM_MODEL_SENTINEL ? "" : value })
                  setEmbeddingTested(false)
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="nomic-embed-text">nomic-embed-text (768d)</SelectItem>
                  <SelectItem value="mxbai-embed-large">mxbai-embed-large (1024d)</SelectItem>
                  <SelectItem value="all-minilm">all-minilm (384d)</SelectItem>
                  <SelectItem value="snowflake-arctic-embed">snowflake-arctic-embed (1024d)</SelectItem>
                  <SelectItem value={CUSTOM_MODEL_SENTINEL}>自定义...</SelectItem>
                </SelectContent>
              </Select>
            </label>

            {/* Custom model input */}
            {!["nomic-embed-text", "mxbai-embed-large", "all-minilm", "snowflake-arctic-embed"].includes(embeddingConfig.model) && (
              <label className="space-y-2 sm:col-span-2">
                <span className="text-sm font-medium">自定义模型名称</span>
                <Input
                  value={embeddingConfig.model}
                  placeholder="输入 Ollama 支持的 embedding 模型名称"
                  onChange={(event) => {
                    setEmbeddingConfig({ model: event.target.value.trim() })
                    setEmbeddingTested(false)
                  }}
                />
              </label>
            )}
          </div>

          {/* Action buttons */}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              onClick={() => testEmbedding.mutate()}
              disabled={testEmbedding.isPending || !embeddingConfig.host || !embeddingConfig.model}
            >
              {testEmbedding.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              测试连接
            </Button>

            <Button
              onClick={() => saveEmbedding.mutate()}
              disabled={saveEmbedding.isPending || !embeddingConfig.host || !embeddingConfig.model}
            >
              {saveEmbedding.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : embeddingSavedId ? (
                <Check className="mr-2 h-4 w-4" />
              ) : (
                <CheckCircle2 className="mr-2 h-4 w-4" />
              )}
              {embeddingSavedId ? "更新并重新注册" : "保存并注册"}
            </Button>

            {embeddingSavedId && (
              <Button
                variant="outline"
                className="text-destructive hover:text-destructive"
                onClick={() => removeEmbedding.mutate()}
                disabled={removeEmbedding.isPending}
              >
                {removeEmbedding.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                删除
              </Button>
            )}
          </div>

          {/* Status feedback */}
          {embeddingSavedId && (
            <div className="mt-4 flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              <span>已绑定: <strong>{embeddingConfig.model}</strong> @ {embeddingConfig.host}</span>
            </div>
          )}

          {testEmbedding.isError && (
            <div className="mt-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{testEmbedding.error instanceof Error ? testEmbedding.error.message : "连接失败"}</span>
            </div>
          )}

          <p className="mt-4 text-xs text-muted-foreground">
            保存后 Embedding 模型会注册到后端 ModelRegistry，知识库上传和查询将自动使用该模型进行向量化。
          </p>
        </section>
      )}
    </ConstructShell>
  )
}
