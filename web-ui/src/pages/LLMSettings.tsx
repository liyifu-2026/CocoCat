import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { providersApi, type ProviderInfo } from "@/api/providers"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, CheckCircle, XCircle, RefreshCw, Eye, EyeOff } from "lucide-react"

export default function LLMSettings() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ["providers"],
    queryFn: () => providersApi.list(),
  })
  const [editing, setEditing] = useState<string | null>(null)
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, { status: string; message?: string }>>({})
  const [refreshing, setRefreshing] = useState(false)

  const providers = data?.providers ?? []

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

  async function refreshCatalog() {
    setRefreshing(true)
    await providersApi.refreshModels()
    setRefreshing(false)
  }

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Configure AI providers, models, and API keys</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={refreshCatalog} disabled={refreshing}>
            <RefreshCw className={`size-3 mr-1 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Model Catalog
          </Button>
        </div>
      </div>

      <div className="grid gap-4">
        {providers.map(provider => (
          <Card key={provider.name}>
            <CardHeader className="flex flex-row items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <CardTitle className="text-base capitalize">{provider.name}</CardTitle>
                {provider.has_key ? (
                  <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50 dark:bg-green-950">
                    <CheckCircle className="size-3 mr-1" /> Configured
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground">
                    <XCircle className="size-3 mr-1" /> Not configured
                  </Badge>
                )}
                {testResult[provider.name]?.status === "ok" && (
                  <Badge variant="outline" className="text-green-600 border-green-300">
                    <CheckCircle className="size-3 mr-1" /> Connected
                  </Badge>
                )}
                {testResult[provider.name]?.status === "error" && (
                  <Badge variant="outline" className="text-red-600 border-red-300">
                    <XCircle className="size-3 mr-1" /> {testResult[provider.name]?.message?.slice(0, 40)}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                {provider.name !== "custom" && (
                  <Button size="xs" variant="outline"
                    onClick={() => testConnection(provider.name)}
                    disabled={testing === provider.name}>
                    {testing === provider.name
                      ? <Loader2 className="size-3 animate-spin" />
                      : "Test"
                    }
                  </Button>
                )}
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
                    <label className="text-xs text-muted-foreground">API Key {provider.has_key ? "(leave blank to keep current)" : ""}</label>
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
                      <Input size={1}
                        value={formData.default_model}
                        onChange={e => setFormData(prev => ({ ...prev, default_model: e.target.value }))}
                        placeholder="gpt-4o"
                        className="mt-0.5"
                      />
                    </div>
                  )}
                  {provider.name === "custom" && (
                    <p className="text-xs text-muted-foreground">
                      For custom providers, enter the full API base URL and any model name.
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
  )
}
