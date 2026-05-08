import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { providersApi, type ProviderInfo, type ModelInfo } from "@/api/providers"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Loader2, CheckCircle, XCircle, RefreshCw, Eye, EyeOff,
  Search, ChevronDown, Globe, Server, Cpu, Cloud, AlertCircle,
} from "lucide-react"
import { toast } from "sonner"

const DISPLAY_NAMES: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  deepseek: "DeepSeek",
  gemini: "Google Gemini",
  siliconflow: "SiliconFlow",
  dashscope: "DashScope (Qwen)",
  zhipu: "Zhipu AI (GLM)",
  openrouter: "OpenRouter",
  groq: "Groq",
  together: "Together AI",
  fireworks: "Fireworks AI",
  deepinfra: "Deep Infra",
  cerebras: "Cerebras",
  xai: "xAI (Grok)",
  moonshot: "Moonshot AI (Kimi)",
  minimax: "MiniMax",
  doubao: "Doubao (ByteDance)",
  baichuan: "Baichuan",
  azure: "Azure OpenAI",
  "aws-bedrock": "Amazon Bedrock",
  ollama: "Ollama (Local)",
  lmstudio: "LM Studio (Local)",
  llamacpp: "llama.cpp (Local)",
  huggingface: "Hugging Face",
  mistral: "Mistral AI",
  cohere: "Cohere",
  replicate: "Replicate",
  perplexity: "Perplexity",
  custom: "Custom (OpenAI-Compatible)",
}

function groupProviders(providers: ProviderInfo[]) {
  const primary = ["openai", "anthropic", "deepseek", "gemini", "siliconflow", "dashscope", "zhipu"]
  const global = ["openrouter", "groq", "together", "fireworks", "deepinfra", "cerebras", "xai"]
  const chinese = ["moonshot", "minimax", "doubao", "baichuan"]
  const cloud = ["azure", "aws-bedrock"]
  const local = ["ollama", "lmstudio", "llamacpp"]
  const other = ["huggingface", "mistral", "cohere", "replicate", "perplexity"]

  const groups: { label: string; icon: typeof Globe; providers: ProviderInfo[]; key: string }[] = [
    { label: "Primary", icon: Server, providers: [], key: "primary" },
    { label: "Global / Proxy", icon: Globe, providers: [], key: "global" },
    { label: "Chinese Providers", icon: Cpu, providers: [], key: "chinese" },
    { label: "Cloud Providers", icon: Cloud, providers: [], key: "cloud" },
    { label: "Local / Self-Hosted", icon: Cpu, providers: [], key: "local" },
    { label: "Other Providers", icon: Globe, providers: [], key: "other" },
    { label: "Custom / Generic", icon: Server, providers: [], key: "custom" },
  ]

  for (const p of providers) {
    let found = false
    for (const list of [primary, global, chinese, cloud, local, other]) {
      if (list.includes(p.name)) {
        const group = groups.find(g => {
          if (list === primary) return g.key === "primary"
          if (list === global) return g.key === "global"
          if (list === chinese) return g.key === "chinese"
          if (list === cloud) return g.key === "cloud"
          if (list === local) return g.key === "local"
          if (list === other) return g.key === "other"
          return false
        })
        if (group) { group.providers.push(p); found = true; break }
      }
    }
    if (!found) {
      if (p.name === "custom") {
        groups.find(g => g.key === "custom")!.providers.push(p)
      } else {
        groups.find(g => g.key === "other")!.providers.push(p)
      }
    }
  }

  return groups.filter(g => g.providers.length > 0)
}

export default function LLMSettings() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["providers"],
    queryFn: () => providersApi.list(),
  })
  const [editing, setEditing] = useState<string | null>(null)
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, { status: string; message?: string; models?: string[] }>>({})
  const [refreshing, setRefreshing] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [fetchedModels, setFetchedModels] = useState<Record<string, ModelInfo[]>>({})
  const [fetchingModels, setFetchingModels] = useState<Record<string, boolean>>({})
  const [modelDropdownOpen, setModelDropdownOpen] = useState<Record<string, boolean>>({})

  const providers = data?.providers ?? []

  function getDisplayName(p: ProviderInfo) {
    return DISPLAY_NAMES[p.name] || (p.name.charAt(0).toUpperCase() + p.name.slice(1))
  }

  async function startEdit(provider: ProviderInfo) {
    setEditing(provider.name)
    setFormData({
      api_base: provider.api_base || "",
      default_model: provider.default_model || "",
      api_key: "",
    })
    setTestResult({})
  }

  async function saveEdit(name: string) {
    await providersApi.update(name, formData)
    queryClient.invalidateQueries({ queryKey: ["providers"] })
    setEditing(null)
    toast.success(`${getDisplayName({ name } as ProviderInfo)} configuration saved`)
  }

  async function testConnection(name: string) {
    setTesting(name)
    setTestResult(prev => ({ ...prev, [name]: { status: "testing" } }))
    try {
      const result = await providersApi.test(name)
      setTestResult(prev => ({ ...prev, [name]: result }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setTestResult(prev => ({ ...prev, [name]: { status: "error", message: msg } }))
    }
    setTesting(null)
  }

  async function fetchModels(name: string) {
    setFetchingModels(prev => ({ ...prev, [name]: true }))
    try {
      const result = await providersApi.fetchProviderModels(name)
      if (result.error) {
        toast.error(`Failed to fetch models: ${result.error}`)
      } else {
        setFetchedModels(prev => ({ ...prev, [name]: result.models }))
        toast.success(`Loaded ${result.models.length} models from ${getDisplayName({ name } as ProviderInfo)}`)
      }
    } catch (e) {
      toast.error(`Error fetching models: ${e instanceof Error ? e.message : String(e)}`)
    }
    setFetchingModels(prev => ({ ...prev, [name]: false }))
  }

  async function refreshCatalog() {
    setRefreshing(true)
    try {
      await providersApi.refreshModels()
      toast.success("Model catalog refreshed")
    } catch {
      toast.error("Failed to refresh catalog")
    }
    setRefreshing(false)
  }

  function toggleModelDropdown(name: string) {
    setModelDropdownOpen(prev => ({ ...prev, [name]: !prev[name] }))
  }

  function selectModel(name: string, modelId: string) {
    setFormData(prev => ({ ...prev, default_model: modelId }))
    setModelDropdownOpen(prev => ({ ...prev, [name]: false }))
  }

  const filteredProviders = searchTerm
    ? providers.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (DISPLAY_NAMES[p.name] || "").toLowerCase().includes(searchTerm.toLowerCase())
      )
    : providers

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6 flex flex-col items-center justify-center h-64 gap-3">
        <AlertCircle className="size-8 text-destructive opacity-50" />
        <p className="text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "Failed to load providers. Is the backend running?"}
        </p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>Retry</Button>
      </div>
    )
  }

  const grouped = groupProviders(filteredProviders)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <p className="text-sm text-muted-foreground">Configure AI providers, API keys, and select models</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-8 h-8 text-sm w-48"
              placeholder="Search providers..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>
          <Button size="sm" variant="outline" onClick={refreshCatalog} disabled={refreshing}>
            <RefreshCw className={`size-3 mr-1 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Catalog
          </Button>
        </div>
      </div>

      {grouped.map(group => (
        <div key={group.key}>
          <div className="flex items-center gap-2 mb-3">
            <group.icon className="size-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">{group.label}</h3>
            <span className="text-xs text-muted-foreground">({group.providers.length})</span>
          </div>
          <div className="grid gap-3">
            {group.providers.map(provider => (
              <Card key={provider.name}>
                <CardHeader className="flex flex-row items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-sm">{getDisplayName(provider)}</CardTitle>
                    {provider.has_key ? (
                      <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50 dark:bg-green-950 text-[10px]">
                        <CheckCircle className="size-3 mr-1" /> Configured
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground text-[10px]">
                        <XCircle className="size-3 mr-1" /> Not configured
                      </Badge>
                    )}
                    {testResult[provider.name]?.status === "ok" && (
                      <Badge variant="outline" className="text-green-600 border-green-300 text-[10px]">
                        <CheckCircle className="size-3 mr-1" /> Connected
                      </Badge>
                    )}
                    {testResult[provider.name]?.status === "error" && (
                      <Badge variant="outline" className="text-red-600 border-red-300 text-[10px]">
                        <XCircle className="size-3 mr-1" /> {testResult[provider.name]?.message?.slice(0, 40)}
                      </Badge>
                    )}
                    {testResult[provider.name]?.status === "testing" && (
                      <Badge variant="outline" className="text-muted-foreground text-[10px]">
                        <Loader2 className="size-3 mr-1 animate-spin" /> Testing...
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {provider.name !== "custom" && editing !== provider.name && (
                      <Button size="xs" variant="outline"
                        onClick={() => fetchModels(provider.name)}
                        disabled={fetchingModels[provider.name]}>
                        {fetchingModels[provider.name]
                          ? <Loader2 className="size-3 animate-spin" />
                          : "Fetch Models"
                        }
                      </Button>
                    )}
                    <Button size="xs" variant="outline"
                      onClick={() => testConnection(provider.name)}
                      disabled={testing === provider.name}>
                      {testing === provider.name
                        ? <Loader2 className="size-3 animate-spin" />
                        : "Test"
                      }
                    </Button>
                    {editing === provider.name ? (
                      <div className="flex gap-1">
                        <Button size="xs" variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
                        <Button size="xs" onClick={() => saveEdit(provider.name)}>Save</Button>
                      </div>
                    ) : (
                      <Button size="xs" variant="outline" onClick={() => startEdit(provider)}>Edit</Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className={editing === provider.name ? "space-y-3" : ""}>
                  {editing === provider.name ? (
                    <>
                      <div>
                        <label className="text-xs text-muted-foreground">
                          API Key {provider.has_key ? "(leave blank to keep current)" : ""}
                        </label>
                        <div className="relative">
                          <Input size={1}
                            type={showKey[provider.name] ? "text" : "password"}
                            value={formData.api_key}
                            onChange={e => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
                            placeholder={provider.has_key ? "●●●●●●●●" : "sk-..."}
                            className="mt-0.5 pr-8"
                          />
                          <button
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            type="button"
                            onClick={() => setShowKey(prev => ({ ...prev, [provider.name]: !prev[provider.name] }))}
                          >
                            {showKey[provider.name] ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Base URL</label>
                        <Input size={1}
                          value={formData.api_base}
                          onChange={e => setFormData(prev => ({ ...prev, api_base: e.target.value }))}
                          placeholder="https://api.openai.com/v1"
                          className="mt-0.5"
                        />
                      </div>
                      {provider.name !== "custom" && (
                        <div>
                          <label className="text-xs text-muted-foreground">Default Model</label>
                          <div className="relative mt-0.5">
                            <button
                              type="button"
                              onClick={() => {
                                if (!fetchedModels[provider.name]) fetchModels(provider.name)
                                toggleModelDropdown(provider.name)
                              }}
                              className="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                            >
                              <span className={formData.default_model ? "" : "text-muted-foreground"}>
                                {formData.default_model || "Select a model..."}
                              </span>
                              <ChevronDown className="size-4 text-muted-foreground" />
                            </button>
                            {modelDropdownOpen[provider.name] && (
                              <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto">
                                <div className="p-2">
                                  <Input
                                    size={1}
                                    placeholder="Filter models..."
                                    className="h-7 text-xs"
                                    autoFocus
                                    onKeyDown={e => e.stopPropagation()}
                                    onChange={e => {
                                      const val = e.target.value.toLowerCase()
                                      const list = fetchedModels[provider.name] || []
                                      if (!val) {
                                        fetchModels(provider.name)
                                      } else {
                                        setFetchedModels(prev => ({
                                          ...prev,
                                          [provider.name]: list.filter(m =>
                                            m.id.toLowerCase().includes(val) ||
                                            (m.name || "").toLowerCase().includes(val)
                                          ),
                                        }))
                                      }
                                    }}
                                  />
                                </div>
                                {!fetchedModels[provider.name] && (
                                  <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                                    Click "Fetch Models" to load available models
                                  </div>
                                )}
                                {fetchedModels[provider.name]?.length === 0 && (
                                  <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                                    No models found or API key not configured
                                  </div>
                                )}
                                {fetchedModels[provider.name]?.map(model => (
                                  <button
                                    key={model.id}
                                    type="button"
                                    onClick={() => selectModel(provider.name, model.id)}
                                    className={`flex w-full items-center px-3 py-1.5 text-sm hover:bg-accent transition-colors ${
                                      formData.default_model === model.id ? "bg-accent/50" : ""
                                    }`}
                                  >
                                    <span className="truncate">{model.id}</span>
                                    {model.name && model.name !== model.id && (
                                      <span className="ml-2 text-xs text-muted-foreground truncate">{model.name}</span>
                                    )}
                                  </button>
                                ))}
                                {fetchingModels[provider.name] && (
                                  <div className="px-3 py-2 text-center text-xs text-muted-foreground">
                                    <Loader2 className="size-3 animate-spin inline mr-1" />
                                    Fetching models...
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      {provider.name === "custom" && (
                        <p className="text-xs text-muted-foreground">
                          For custom providers, enter the full API base URL and any model name.
                          Supports any OpenAI-compatible or Anthropic-compatible API.
                        </p>
                      )}
                    </>
                  ) : (
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground text-xs">API Key</span>
                        <p className="font-mono text-xs mt-0.5">{provider.key_masked || "—"}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-xs">Base URL</span>
                        <p className="font-mono text-xs mt-0.5 truncate">{provider.api_base || "—"}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-xs">Default Model</span>
                        <p className="text-xs mt-0.5">{provider.default_model || "—"}</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
