import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Check, Cpu, Eye, EyeOff, KeyRound, RefreshCw, Terminal } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { listAgents } from "@/services/models"
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
  const mode = useProviderStore((s) => s.mode)
  const byok = useProviderStore((s) => s.byok)
  const selectedAgentId = useProviderStore((s) => s.selectedAgentId)
  const agentModels = useProviderStore((s) => s.agentModels)
  const setMode = useProviderStore((s) => s.setMode)
  const setByok = useProviderStore((s) => s.setByok)
  const setApiProtocol = useProviderStore((s) => s.setApiProtocol)
  const setSelectedAgentId = useProviderStore((s) => s.setSelectedAgentId)
  const setAgentModelChoice = useProviderStore((s) => s.setAgentModelChoice)
  const setChatModel = useChatStore((s) => s.setModel)

  const agentsQuery = useQuery({
    queryKey: ["agents", "list"],
    queryFn: listAgents,
    staleTime: 10_000,
  })

  const agents = agentsQuery.data?.agents || []
  const availableAgents = agents.filter((agent) => agent.available)
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId)
  const selectedChoice = selectedAgentId ? agentModels[selectedAgentId] ?? {} : {}

  const chooseAgent = (agentId: string) => {
    setSelectedAgentId(agentId)
    setMode("daemon")
    setChatModel(agentId)
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
          在本机 CLI 和 BYOK API 之间切换。CLI 使用本机登录态，BYOK 使用你自己的 API key。
        </p>
      </div>

      <div className="mb-5 grid grid-cols-2 rounded-lg border border-border bg-muted/40 p-1">
        <button
          type="button"
          onClick={() => setMode("daemon")}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "daemon" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          )}
        >
          本机 CLI
        </button>
        <button
          type="button"
          onClick={() => setMode("api")}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition-colors",
            mode === "api" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          )}
        >
          BYOK API
        </button>
      </div>

      {mode === "daemon" ? (
        <>
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h4 className="m-0 text-sm font-semibold">本机 CLI</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                选择已安装的 Claude Code 或 Codex CLI。认证和 API key 由本机 CLI 自己管理。
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
      ) : (
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
            API key 只保存在浏览器本地，并随请求发送到本机后端代理，再由后端转发到对应上游。
          </p>
        </section>
      )}
    </ConstructShell>
  )
}
