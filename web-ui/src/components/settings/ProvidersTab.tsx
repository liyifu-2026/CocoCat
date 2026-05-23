import { useState, useEffect, useRef, useMemo } from "react"
import { useT } from "@/context/LanguageContext"
import { Loader2, Plus, Trash2, Eye, EyeOff, CheckCircle2, XCircle, ChevronsRight, ChevronRight, ChevronLeft, ChevronsLeft, Search } from "lucide-react"
import { toast } from "sonner"
import { PROVIDER_ICONS } from "@/lib/provider-icons"
import { getCatalogModels, getCatalogMeta, isProviderSupported } from "@/lib/model-catalog"
import type { ProviderInfo, TabData } from "@/types/settings"
import type { Model } from "modelpedia"
// ── Color palette for provider logos ──

const LOGO_COLORS = [
  "bg-blue-500/15 text-blue-400", "bg-emerald-500/15 text-emerald-400", "bg-orange-500/15 text-orange-400",
  "bg-purple-500/15 text-purple-400", "bg-cyan-500/15 text-cyan-400", "bg-rose-500/15 text-rose-400",
  "bg-amber-500/15 text-amber-400", "bg-lime-500/15 text-lime-400", "bg-teal-500/15 text-teal-400",
  "bg-indigo-500/15 text-indigo-400", "bg-pink-500/15 text-pink-400", "bg-sky-500/15 text-sky-400",
  "bg-fuchsia-500/15 text-fuchsia-400", "bg-green-500/15 text-green-400",
]

function logoColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return LOGO_COLORS[Math.abs(hash) % LOGO_COLORS.length]!
}

function logoLetters(name: string): string {
  return name.replace(/[^a-zA-Z]/g, "").slice(0, 2).toUpperCase()
}

function ModelMetaTooltip({ model }: { model: Model }) {
  const t = useT()
  const lines: string[] = []
  if (model.context_window) lines.push(`${t("provider.tooltip_context")} ${(model.context_window / 1000).toFixed(0)}k tokens`)
  if (model.max_output_tokens) lines.push(`${t("provider.tooltip_max_output")} ${(model.max_output_tokens / 1000).toFixed(0)}k tokens`)
  if (model.pricing) {
    const cost = `$${model.pricing.input}/$${model.pricing.output} (per million tokens)`
    lines.push(`${t("provider.tooltip_pricing")} ${cost}`)
  }
  if (model.status) lines.push(`${t("provider.tooltip_status")} ${model.status}`)
  if (!lines.length) return null
  return (
    <div className="invisible group-hover:visible absolute bottom-full left-0 mb-1 z-50 w-56 bg-slate-800 text-slate-100 text-[10px] rounded-lg px-3 py-2 shadow-lg leading-relaxed">
      {lines.map((l, i) => <div key={i}>{l}</div>)}
    </div>
  )
}

// ── Providers Tab ──

export function ProvidersTab({ data, onUpdate }: { data: TabData; onUpdate: () => void }) {
  const t = useT()
  const providers = (data?.providers || []) as ProviderInfo[]
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [customName, setCustomName] = useState("")
  const [customDisplayName, setCustomDisplayName] = useState("")
  const [customUrl, setCustomUrl] = useState("")
  const [addingCustom, setAddingCustom] = useState(false)

  const sorted = [...providers].sort((a, b) => {
    if (a.connected && !b.connected) return -1
    if (!a.connected && b.connected) return 1
    return (a.display_name || a.name).localeCompare(b.display_name || b.name)
  })

  const selected = sorted.find(p => p.name === selectedId) || sorted[0] || null
  const hasConfigured = sorted.some(p => p.connected)

  // Auto-select first provider if none selected
  const effectiveSelected: string | undefined = selectedId || sorted[0]?.name || undefined

  const handleAddCustom = async () => {
    const name = customName.trim().toLowerCase().replace(/\s+/g, "-")
    if (!name || !customUrl.trim()) return
    await fetch(`/api/providers/${encodeURIComponent(name)}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: customDisplayName.trim() || name, base_url: customUrl.trim() }),
    })
    setCustomName(""); setCustomDisplayName(""); setCustomUrl(""); setAddingCustom(false)
    setSelectedId(name)
    onUpdate()
  }

  return (
    <div className="flex gap-0 h-[480px] min-w-0">
      {/* Left column — fixed width, not percentage */}
      <div className="w-[230px] shrink-0 border-r border-border/50 overflow-y-auto flex flex-col">
        {hasConfigured && (
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">{t("provider.configured")}</div>
        )}
        {sorted.filter(p => p.connected).map(p => (
          <ProviderListItem key={p.name} provider={p} active={effectiveSelected === p.name} onClick={() => { setSelectedId(p.name); setAddingCustom(false) }} />
        ))}
        {hasConfigured && (
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2 mt-1">{t("provider.unconfigured")}</div>
        )}
        {sorted.filter(p => !p.connected).map(p => (
          <ProviderListItem key={p.name} provider={p} active={effectiveSelected === p.name} onClick={() => { setSelectedId(p.name); setAddingCustom(false) }} />
        ))}
        <div className="p-2 mt-auto">
          {addingCustom ? (
            <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 space-y-2">
              <input value={customName} onChange={e => setCustomName(e.target.value)} placeholder={t("provider.id_placeholder")} className="w-full rounded border border-blue-500/30 bg-card px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
              <input value={customDisplayName} onChange={e => setCustomDisplayName(e.target.value)} placeholder={t("provider.display_name_placeholder")} className="w-full rounded border border-blue-500/30 bg-card px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
              <input value={customUrl} onChange={e => setCustomUrl(e.target.value)} placeholder={t("provider.base_url_placeholder")} className="w-full rounded border border-blue-500/30 bg-card px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
              <div className="flex gap-2">
                <button onClick={handleAddCustom} disabled={!customName.trim() || !customUrl.trim()} className="flex-1 rounded bg-blue-600 text-white px-3 py-1.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-40 transition-all">{t("provider.add")}</button>
                <button onClick={() => { setAddingCustom(false); setCustomName(""); setCustomDisplayName(""); setCustomUrl("") }} className="rounded border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-all">{t("provider.cancel")}</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setAddingCustom(true)} className="w-full rounded-lg border border-dashed border-border/60 px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-all">
              <Plus className="size-3 inline mr-1" /> {t("provider.custom_provider")}
            </button>
          )}
        </div>
      </div>

      {/* Right column */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-5 min-w-0">
        {effectiveSelected ? (
          <ProviderDetailPanel key={effectiveSelected} providerName={effectiveSelected} provider={selected ?? undefined} onUpdate={onUpdate} />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground/50">{t("provider.select_left")}</div>
        )}
      </div>
    </div>
  )
}

export function ProviderListItem({ provider, active, onClick }: { provider: ProviderInfo; active: boolean; onClick: () => void }) {
  const t = useT()
  const IconComp = PROVIDER_ICONS[provider.name]
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 text-left rounded-lg transition-all duration-150 ${
        active ? "bg-blue-500/10 border border-blue-500/30" : "hover:bg-muted/40 border border-transparent"
      } ${!provider.connected ? "opacity-65" : ""}`}
    >
      <div className={`size-8 rounded-lg flex items-center justify-center shrink-0 ${logoColor(provider.name)}`}>
        {IconComp ? <IconComp size={18} /> : <span className="text-xs font-bold">{logoLetters(provider.display_name || provider.name)}</span>}
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-sm truncate ${active ? "font-medium text-foreground" : "text-foreground/80"}`}>
          {provider.display_name || provider.name}
        </div>
        {provider.connected && (
          <div className="text-[10px] text-muted-foreground">{provider.enabled_count}{t("provider.model_count")}</div>
        )}
      </div>
      <span className={`size-2 rounded-full shrink-0 ${provider.connected ? "bg-green-500" : "bg-muted-foreground/30"}`} />
    </button>
  )
}

// ── Provider Detail Panel ──

interface ModelData {
  available: string[]
  enabled: string[]
  default: string
}

export function ProviderDetailPanel({ providerName, provider, onUpdate }: { providerName: string; provider?: ProviderInfo; onUpdate: () => void }) {
  const t = useT()
  const [keyVal, setKeyVal] = useState("")
  const [baseUrl, setBaseUrl] = useState(provider?.base_url || "")
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [connStatus, setConnStatus] = useState<"idle" | "ok" | "fail">(provider?.connected ? "ok" : "idle")
  const [connError, setConnError] = useState("")
  const [models, setModels] = useState<ModelData>({ available: [], enabled: [], default: "" })
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [manualModel, setManualModel] = useState("")
  const [checkedAvailable, setCheckedAvailable] = useState<Set<string>>(new Set())
  const [dragId, setDragId] = useState<string | null>(null)
  const [modelSearch, setModelSearch] = useState("")

  // Load base_url from provider info
  useEffect(() => {
    if (provider) setBaseUrl(provider.base_url)
  }, [provider?.base_url])

  // Load saved API key from backend
  const [savedKey, setSavedKey] = useState("")
  useEffect(() => {
    fetch(`/api/providers/${encodeURIComponent(providerName)}/config`)
      .then((r) => r.json())
      .then((d) => { if (d.key) { setSavedKey(d.key); setKeyVal(d.key) } })
      .catch(() => {})
  }, [providerName])

  // Load enabled models from backend
  useEffect(() => {
    fetch(`/api/providers/${encodeURIComponent(providerName)}/models`)
      .then((r) => r.json())
      .then((d) => {
        if (d.enabled) {
          setModels((prev) => ({
            ...prev,
            enabled: d.enabled || [],
            default: d.default || "",
          }))
        }
        setModelsLoaded(true)
      })
      .catch(() => setModelsLoaded(true))
  }, [providerName])

  // Build available models from modelpedia catalog + API-discovered
  const catalogModels = useMemo(() => {
    if (!provider) return [] as Model[]
    return getCatalogModels(providerName)
  }, [providerName, provider])

  const mergedAvailable = useMemo(() => {
    const catalogIds = new Set(catalogModels.map((m) => m.id))
    const merged = [...catalogModels.map((m) => m.id)]
    for (const m of (discoveredModels || [])) {
      if (!catalogIds.has(m)) merged.push(m)
    }
    // If modelpedia doesn't cover this provider, use backend available
    if (catalogModels.length === 0) {
      return [...new Set([...merged, ...models.available])].filter(
        (id) => !models.enabled.includes(id),
      )
    }
    return merged.filter((id) => !models.enabled.includes(id))
  }, [catalogModels, discoveredModels, models.available, models.enabled])

  // Precompute model metadata map for O(1) lookup
  const catalogMetaMap = useMemo(
    () => new Map(catalogModels.map((m) => [m.id, m])),
    [catalogModels],
  )

  const availModels = useMemo(
    () =>
      mergedAvailable.filter(
        (m) =>
          !modelSearch || m.toLowerCase().includes(modelSearch.toLowerCase()),
      ),
    [mergedAvailable, modelSearch],
  )

  const handleSave = async () => {
    if (!keyVal.trim()) return
    setSaving(true)
    setConnStatus("idle")
    setConnError("")
    const start = performance.now()
    try {
      const resp = await fetch("/api/providers/key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: providerName, key: keyVal.trim() }),
      })
      const data = await resp.json()
      const elapsed = Math.round(performance.now() - start)
      if (data.ok) {
        setConnStatus("ok")
        setSavedKey(keyVal.trim())
        toast.success(t("provider.toast_connected") + ` · ${data.latency_ms ?? elapsed}ms`, { duration: 3000 })
      } else {
        setConnStatus("fail")
        setConnError(data.error || "Connection failed")
        toast.error(data.error || t("provider.toast_failed"), { description: `${data.latency_ms ?? elapsed}ms`, duration: 4000 })
      }
      onUpdate()
    } catch {
      setConnStatus("fail")
      setConnError("Network error")
      toast.error(t("provider.toast_network_error"))
    }
    finally { setSaving(false) }
  }

  const handleSaveUrl = async () => {
    const url = baseUrl.trim()
    if (!url) return
    await fetch(`/api/providers/${encodeURIComponent(providerName)}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_url: url }),
    })
    onUpdate()
  }

  const handleFetchModels = async () => {
    setFetching(true)
    try {
      const resp = await fetch("/api/providers/fetch-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: providerName, base_url: baseUrl, key: keyVal.trim() || undefined }),
      })
      const data = await resp.json()
      if (data.models?.length) {
        setDiscoveredModels(data.models)
        const newAvailable = [...new Set([...models.available, ...data.models])]
        setModels(prev => ({ ...prev, available: newAvailable }))
        await syncModels(models.enabled, models.default)
      }
    } catch {} finally { setFetching(false) }
  }

  const syncModels = async (enabled: string[], defaultModel: string) => {
    await fetch(`/api/providers/${encodeURIComponent(providerName)}/models/batch`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ models: enabled, default: defaultModel || null }),
    })
  }

  const moveToEnabled = async (ids: string[]) => {
    if (!ids.length) return
    const newEnabled = [...models.enabled, ...ids.filter(id => !models.enabled.includes(id))]
    const newAvail = models.available.filter(m => !newEnabled.includes(m))
    const newDefault = models.default && !newEnabled.includes(models.default) ? (newEnabled[0] || "") : models.default
    setModels({ available: newAvail, enabled: newEnabled, default: newDefault || (newEnabled[0] || "") })
    setCheckedAvailable(new Set())
    await syncModels(newEnabled, newDefault || (newEnabled[0] || ""))
    onUpdate()
  }

  const moveToAvailable = async (ids: string[]) => {
    if (!ids.length) return
    const newEnabled = models.enabled.filter(m => !ids.includes(m))
    const newAvail = [...new Set([...models.available, ...ids])]
    const newDefault = ids.includes(models.default) ? (newEnabled[0] || "") : models.default
    setModels({ available: newAvail, enabled: newEnabled, default: newDefault })
    await syncModels(newEnabled, newDefault)
    onUpdate()
  }

  const setDefault = async (id: string) => {
    const newDefault = id
    setModels(prev => ({ ...prev, default: newDefault }))
    await syncModels(models.enabled, newDefault)
    onUpdate()
  }

  const addManual = async () => {
    const val = manualModel.trim()
    if (!val || models.enabled.includes(val)) return
    const newEnabled = [...models.enabled, val]
    setModels(prev => ({ ...prev, enabled: newEnabled, available: prev.available.filter(m => m !== val) }))
    setManualModel("")
    await syncModels(newEnabled, models.default)
    onUpdate()
  }

  const handleDelete = async () => {
    if (provider?.custom) {
      await fetch(`/api/providers/${encodeURIComponent(providerName)}`, { method: "DELETE" })
      onUpdate()
    } else {
      await fetch("/api/providers/key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: providerName, key: "" }),
      })
      setModels({ available: [], enabled: [], default: "" })
      setConnStatus("idle")
      setConnError("")
      onUpdate()
    }
  }

  // Drag handlers
  const onDragStart = (e: React.DragEvent, id: string) => { setDragId(id); e.dataTransfer.effectAllowed = "move" }
  const onDragEnd = () => setDragId(null)
  const onDropToEnabled = async (e: React.DragEvent) => {
    e.preventDefault()
    if (dragId) await moveToEnabled([dragId])
    setDragId(null)
  }
  const onDropToAvail = async (e: React.DragEvent) => {
    e.preventDefault()
    if (dragId) await moveToAvailable([dragId])
    setDragId(null)
  }

  const isConnected = connStatus === "ok"
  const IconComp = PROVIDER_ICONS[providerName]

  return (
    <div className="space-y-4 py-3">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className={`size-9 rounded-lg flex items-center justify-center shrink-0 ${logoColor(providerName)}`}>
          {IconComp ? <IconComp size={20} /> : <span className="text-xs font-bold">{logoLetters(provider?.display_name || providerName)}</span>}
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-foreground">{provider?.display_name || providerName}</h3>
          <p className="text-[10px] text-muted-foreground truncate">{baseUrl}</p>
        </div>
        <span className={`ml-auto shrink-0 text-[10px] px-2 py-0.5 rounded-full font-medium ${isConnected ? "bg-green-500/15 text-green-300" : "bg-muted text-muted-foreground"}`}>
          {isConnected ? t("provider.connected") : t("provider.unconfigured")}
        </span>
      </div>

      {/* API Key */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-muted-foreground">{t("provider.api_key_label")}</label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type={showKey ? "text" : "password"}
              placeholder={savedKey ? t("provider.api_key_saved_placeholder") : t("provider.api_key_placeholder")}
              value={keyVal}
              onChange={e => { setKeyVal(e.target.value); setConnStatus("idle"); setConnError("") }}
              onKeyDown={e => { if (e.key === "Enter") handleSave() }}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 pr-14"
            />
            <button onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground">
              {showKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            </button>
          </div>
          <button onClick={handleSave} disabled={!keyVal.trim() || saving} className="shrink-0 rounded-lg bg-blue-600 text-white px-4 py-2 text-xs font-medium hover:bg-blue-700 disabled:opacity-40 active:scale-95 transition-all flex items-center gap-1.5">
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
            {t("provider.save_and_test")}
          </button>
        </div>
        {connStatus === "ok" && (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="size-1.5 rounded-full bg-green-500" />
            <span className="text-green-400">{t("provider.connection_ok")}</span>
          </div>
        )}
        {connStatus === "fail" && (
          <div className="flex items-center gap-1.5 text-xs">
            <XCircle className="size-3 text-red-400" />
            <span className="text-red-400">{connError || t("provider.connection_fail")}</span>
          </div>
        )}
      </div>

      {/* Base URL */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-muted-foreground">{t("provider.base_url_label")}</label>
        <input
          type="text"
          value={baseUrl}
          onChange={e => setBaseUrl(e.target.value)}
          onBlur={handleSaveUrl}
          onKeyDown={e => { if (e.key === "Enter") handleSaveUrl() }}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
        />
      </div>

      {/* Models */}
      {isConnected && modelsLoaded && (
        <div className="space-y-2 border-t border-border/50 pt-3">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-medium text-muted-foreground">{t("provider.models_label")}</label>
            <button onClick={handleFetchModels} disabled={fetching} className="text-[10px] text-blue-400 hover:text-blue-300 font-medium disabled:opacity-50">
              {fetching ? <Loader2 className="size-3 animate-spin inline" /> : t("provider.fetch_models")}
            </button>
          </div>
          <div className="flex gap-1.5 h-[200px] min-w-0">
            {/* Available */}
            <div
              className="flex-1 min-w-[100px] flex flex-col rounded-lg border border-border bg-muted/20"
              onDragOver={e => e.preventDefault()}
              onDrop={onDropToAvail}
            >
              <div className="px-3 py-1.5 text-[10px] text-muted-foreground uppercase font-medium border-b border-border/30 shrink-0 space-y-1">
                <div>{t("provider.available_models")}</div>
                <div className="relative">
                  <Search className="size-3 absolute left-1.5 top-1/2 -translate-y-1/2 text-muted-foreground/50" />
                  <input
                    value={modelSearch}
                    onChange={e => setModelSearch(e.target.value)}
                    placeholder={t("provider.filter_placeholder")}
                    className="w-full rounded border border-border/50 bg-card pl-5 pr-2 py-0.5 text-[10px] font-normal normal-case focus:outline-none focus:ring-1 focus:ring-blue-400/30"
                  />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-1">
                {availModels.map(m => {
                  const meta = catalogMetaMap.get(m)
                  return (
                    <div
                      key={m}
                      draggable
                      onDragStart={e => onDragStart(e, m)}
                      onDragEnd={onDragEnd}
                      className={`group relative flex items-center gap-2 px-2 py-1.5 rounded hover:bg-background cursor-pointer text-xs mb-0.5 transition-colors ${dragId === m ? "opacity-40" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={checkedAvailable.has(m)}
                        onChange={() => {
                          const next = new Set(checkedAvailable)
                          next.has(m) ? next.delete(m) : next.add(m)
                          setCheckedAvailable(next)
                        }}
                        className="rounded border-border shrink-0"
                      />
                      <span className="text-foreground truncate flex-1">{m}</span>
                      {meta?.status === "deprecated" && (
                        <span className="text-[9px] px-1 py-0 rounded bg-amber-500/15 text-amber-400 shrink-0">{t("provider.deprecated")}</span>
                      )}
                      {meta?.status === "active" && (
                        <span className="text-[9px] px-1 py-0 rounded bg-green-500/15 text-green-400 shrink-0">{t("provider.active")}</span>
                      )}
                      {meta && <ModelMetaTooltip model={meta} />}
                    </div>
                  )
                })}
                {availModels.length === 0 && (
                  <div className="text-[10px] text-muted-foreground/40 text-center py-8">{t("provider.all_enabled")}</div>
                )}
              </div>
            </div>

            {/* Arrows */}
            <div className="flex flex-col justify-center gap-1.5 shrink-0">
              <button onClick={() => moveToEnabled(availModels.map(m => m))} disabled={availModels.length === 0} className="size-6 rounded border border-border bg-background hover:bg-blue-500/15 hover:border-blue-500/40 flex items-center justify-center text-muted-foreground hover:text-blue-400 transition-all disabled:opacity-30" title={t("provider.move_all_in")}>
                <ChevronsRight className="size-3" />
              </button>
              <button onClick={() => moveToEnabled([...checkedAvailable])} disabled={checkedAvailable.size === 0} className="size-6 rounded border border-border bg-background hover:bg-blue-500/15 hover:border-blue-500/40 flex items-center justify-center text-muted-foreground hover:text-blue-400 transition-all disabled:opacity-30" title={t("provider.move_selected_in")}>
                <ChevronRight className="size-3" />
              </button>
              <button onClick={() => moveToAvailable(models.enabled.filter(m => m !== models.default))} disabled={models.enabled.length <= 1} className="size-6 rounded border border-border bg-background hover:bg-blue-500/15 hover:border-blue-500/40 flex items-center justify-center text-muted-foreground hover:text-blue-400 transition-all disabled:opacity-30" title={t("provider.move_non_default_out")}>
                <ChevronLeft className="size-3" />
              </button>
              <button onClick={() => moveToAvailable([...models.enabled])} disabled={models.enabled.length === 0} className="size-6 rounded border border-border bg-background hover:bg-blue-500/15 hover:border-blue-500/40 flex items-center justify-center text-muted-foreground hover:text-blue-400 transition-all disabled:opacity-30" title={t("provider.move_all_out")}>
                <ChevronsLeft className="size-3" />
              </button>
            </div>

            {/* Enabled */}
            <div
              className="flex-1 min-w-[100px] flex flex-col rounded-lg border border-blue-500/30 bg-blue-500/10"
              onDragOver={e => e.preventDefault()}
              onDrop={onDropToEnabled}
            >
              <div className="px-3 py-1.5 text-[10px] text-blue-400 uppercase font-medium border-b border-blue-500/30 shrink-0 flex items-center justify-between">
                <span>{t("provider.enabled_models")} · {models.enabled.length}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-1">
                {models.enabled.map(m => (
                  <div
                    key={m}
                    draggable
                    onDragStart={e => onDragStart(e, m)}
                    onDragEnd={onDragEnd}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded bg-card border border-blue-500/30 text-xs mb-0.5 transition-colors ${dragId === m ? "opacity-40" : ""}`}
                  >
                    <span className={`size-1.5 rounded-full shrink-0 ${m === models.default ? "bg-blue-500" : "bg-blue-300"}`} />
                    <span className={`flex-1 truncate ${m === models.default ? "font-medium text-foreground" : "text-muted-foreground"}`}>{m}</span>
                    {m === models.default ? (
                      <span className="text-[9px] px-1 py-0 rounded bg-blue-500/15 text-blue-400 font-medium shrink-0">{t("provider.default")}</span>
                    ) : (
                      <button onClick={() => setDefault(m)} className="text-[9px] text-muted-foreground/50 hover:text-blue-500 shrink-0">{t("provider.set_default")}</button>
                    )}
                    <button onClick={() => moveToAvailable([m])} className="text-muted-foreground/50 hover:text-red-400 shrink-0">×</button>
                  </div>
                ))}
                {models.enabled.length === 0 && (
                  <div className="text-[10px] text-muted-foreground/40 text-center py-8">{t("provider.drag_from_left")}</div>
                )}
              </div>
              <div className="p-2 border-t border-blue-500/30 shrink-0">
                <div className="flex gap-1">
                  <input
                    value={manualModel}
                    onChange={e => setManualModel(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") addManual() }}
                    placeholder={t("provider.manual_model_placeholder")}
                    className="flex-1 rounded border border-blue-500/30 bg-card px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                  />
                  <button onClick={addManual} disabled={!manualModel.trim()} className="shrink-0 rounded bg-blue-500 text-white px-2 py-1 text-xs hover:bg-blue-600 disabled:opacity-30 transition-all">{t("provider.add")}</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Danger zone */}
      {isConnected && (
        <div className="pt-3 border-t border-border/50">
          <button onClick={handleDelete} className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 font-medium transition-colors">
            <Trash2 className="size-3" />
            {provider?.custom ? t("provider.delete_provider") : t("provider.remove_key")}
          </button>
        </div>
      )}
    </div>
  )
}

