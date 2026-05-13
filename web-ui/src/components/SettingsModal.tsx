import { useState, useEffect, useRef } from "react"
import { X, Loader2, Cpu, Plug, Layers, Wrench, Book, Radio, Palette, Settings } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { useLang } from "@/context/LanguageContext"
import { useTheme } from "@/context/ThemeContext"

interface TabItem { label: string; icon: LucideIcon }

const TABS: TabItem[] = [
  { label: "智能体", icon: Cpu },
  { label: "供应商", icon: Plug },
  { label: "场景", icon: Layers },
  { label: "技能", icon: Wrench },
  { label: "知识库", icon: Book },
  { label: "渠道", icon: Radio },
  { label: "外观", icon: Palette },
  { label: "通用", icon: Settings },
]

function NavBtn({ item, index, active, onSelect }: { item: TabItem; index: number; active: boolean; onSelect: (i: number) => void }) {
  const Icon = item.icon
  return (
    <button
      onClick={() => onSelect(index)}
      className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-all duration-200 flex items-center gap-2.5 ${
        active
          ? "bg-tertiary text-tertiary-foreground font-medium shadow-sm"
          : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
      }`}
    >
      <Icon className="size-4 shrink-0" />
      <span>{item.label}</span>
    </button>
  )
}

interface TabData {
  agents?: { id: string; name: string; role: string; model: string; status: string }[]
  providers?: { name: string; display_name: string; base_url: string; env_key: string; has_key: boolean }[]
  scenes?: { id: string; name?: string; kbs?: string[]; skills?: string[] }[]
  global?: { name: string; description: string }[]
  kbs?: { id: string; purpose?: string }[]
  channels?: { channel_type: string; target_type: string; target_id: string; status: string }[]
}

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [tab, setTab] = useState(0)
  const [data, setData] = useState<TabData>({})
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!open) return
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort
    const endpoints: Record<number, string> = {
      0: "/api/agents",
      1: "/api/providers",
      2: "/api/scenes",
      3: "/api/skills",
      4: "/api/knowledge",
      5: "/api/channels",
    }
    const url = endpoints[tab]
    if (url) fetch(url, { signal: abort.signal }).then(r => r.json()).then(d => { if (!abort.signal.aborted) setData(d) }).catch(() => {})
    return () => abort.abort()
  }, [tab, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-[620px] w-[840px] rounded-2xl bg-card shadow-2xl border border-border/50 overflow-hidden animate-in"
        onClick={e => e.stopPropagation()}
        style={{ animation: "fadeSlideUp 0.2s ease-out both" }}
      >
        {/* Left nav */}
        <nav className="w-48 border-r border-border bg-muted/30 p-3 space-y-1">
          {TABS.map((item, i) => (
            <NavBtn key={item.label} item={item} index={i} active={tab === i} onSelect={setTab} />
          ))}
        </nav>

        {/* Right content */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between border-b border-border px-5 h-13 shrink-0">
            <h2 className="text-sm font-display text-foreground">{TABS[tab]?.label ?? ""}</h2>
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200">
              <X className="size-4" />
            </button>
          </div>
          <div className="flex-1 overflow-auto p-5">
            <SettingsContent tab={tab} data={data} onUpdate={() => {
              const endpoints: Record<number, string> = {
                0: "/api/agents", 2: "/api/scenes", 3: "/api/skills",
                4: "/api/knowledge", 5: "/api/channels",
              }
              const url = endpoints[tab]
              if (url) fetch(url).then(r => r.json()).then(setData)
            }} />
          </div>
        </div>
      </div>
    </div>
  )
}

function SettingsContent({ tab, data, onUpdate }: { tab: number; data: TabData; onUpdate: () => void }) {
  switch (tab) {
    case 0: return <AgentsTab data={data} />
    case 1: return <ProvidersTab data={data} onUpdate={onUpdate} />
    case 2: return <ScenesTab data={data} />
    case 3: return <SkillsTab data={data} />
    case 4: return <KBTab data={data} onUpdate={onUpdate} />
    case 5: return <ChannelsTab data={data} />
    case 6: return <AppearanceTab />
    case 7: return <GeneralTab />
    default: return null
  }
}

function AgentsTab({ data }: { data: TabData }) {
  const agents = data?.agents || []
  return (
    <div className="space-y-3 stagger-1">
      {agents.map((a: { id: string; name: string; role: string; model: string; status: string }) => (
        <div key={a.id} className="rounded-xl border border-border/60 bg-card p-4 hover:shadow-sm transition-shadow duration-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-foreground">{a.name}</h3>
              <p className="text-xs text-muted-foreground/70 mt-0.5">ID: {a.id} · Role: {a.role} · Model: {a.model}</p>
            </div>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              a.status === "running" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
            }`}>
              {a.status || "stopped"}
            </span>
          </div>
        </div>
      ))}
      <p className="text-xs text-muted-foreground/50 pt-1">
        Agent management via admin panel. Main AI always present.
      </p>
    </div>
  )
}

function ProvidersTab({ data, onUpdate }: { data: TabData; onUpdate: () => void }) {
  const providers = data?.providers || []
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [addingCustom, setAddingCustom] = useState(false)

  // Sort: configured first, then unconfigured
  const sorted = [...providers].sort((a, b) => {
    if (a.has_key && !b.has_key) return -1
    if (!a.has_key && b.has_key) return 1
    return (a.display_name || a.name).localeCompare(b.display_name || b.name)
  })

  const selected = sorted.find(p => p.name === selectedId)
  const hasConfigured = sorted.some(p => p.has_key)

  return (
    <div className="flex gap-0 h-[480px]">
      {/* Left column: provider list */}
      <div className="w-[38%] border-r border-border/50 overflow-y-auto pr-1">
        {hasConfigured && (
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-2 py-1.5">Configured</div>
        )}
        {sorted.filter(p => p.has_key).map(p => (
          <button
            key={p.name}
            onClick={() => setSelectedId(p.name)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-left rounded-lg transition-all duration-150 text-sm ${
              selectedId === p.name ? "bg-accent text-accent-foreground font-medium" : "hover:bg-muted/40 text-foreground/80"
            }`}
          >
            <span className={`size-2 rounded-full shrink-0 ${p.has_key ? "bg-green-500" : "bg-muted-foreground/30"}`} />
            <span className="truncate">{p.display_name || p.name}</span>
          </button>
        ))}

        {hasConfigured && (
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-2 py-2 mt-2">Available</div>
        )}
        {sorted.filter(p => !p.has_key).map(p => (
          <button
            key={p.name}
            onClick={() => setSelectedId(p.name)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-left rounded-lg transition-all duration-150 text-sm ${
              selectedId === p.name ? "bg-accent text-accent-foreground font-medium" : "hover:bg-muted/40 text-foreground/60 opacity-60"
            }`}
          >
            <span className="size-2 rounded-full shrink-0 bg-muted-foreground/30" />
            <span className="truncate">{p.display_name || p.name}</span>
          </button>
        ))}

        <div className="px-2 pt-3">
          <button
            onClick={() => setAddingCustom(true)}
            className="w-full rounded-lg border border-dashed border-border/60 px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-all duration-200"
          >
            + Add Custom Provider
          </button>
        </div>
      </div>

      {/* Right column: detail */}
      <div className="flex-1 overflow-y-auto px-4">
        {selected ? (
          <ProviderDetailPanel
            key={selected.name}
            provider={selected}
            onUpdate={() => { onUpdate(); setSelectedId(selected.name) }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground/50">
            Select a provider from the left
          </div>
        )}
      </div>

      {/* Add custom provider overlay */}
      {addingCustom && (
        <AddCustomOverlay
          onDone={() => { setAddingCustom(false); onUpdate() }}
          onCancel={() => setAddingCustom(false)}
        />
      )}
    </div>
  )
}

function ProviderDetailPanel({ provider, onUpdate }: { provider: { name: string; display_name: string; base_url: string; has_key: boolean; env_key: string }; onUpdate: () => void }) {
  const [keyVal, setKeyVal] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [connStatus, setConnStatus] = useState<"idle" | "ok" | "fail">("idle")
  const [models, setModels] = useState<string[]>([])
  const [newModel, setNewModel] = useState("")
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    fetch(`/api/providers/${provider.name}/models`).then(r => r.json()).then(d => setModels(d.models || [])).catch(() => {})
  }, [provider.name])

  const handleSave = async () => {
    if (!keyVal.trim()) return
    setSaving(true)
    try {
      await fetch("/api/providers/key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: provider.name, key: keyVal.trim() }),
      })
      setKeyVal("")
      setConnStatus("idle")
      onUpdate()
    } catch {} finally { setSaving(false) }
  }

  const handleTest = async () => {
    const testKey = keyVal.trim() || (provider.has_key ? "" : "")
    setTesting(true)
    setConnStatus("idle")
    try {
      const resp = await fetch("/api/providers/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: provider.name, base_url: provider.base_url, key: testKey || undefined }),
      })
      const data = await resp.json()
      setConnStatus(data.ok ? "ok" : "fail")
    } catch { setConnStatus("fail") }
    finally { setTesting(false) }
  }

  const handleFetchModels = async () => {
    setFetching(true)
    try {
      const resp = await fetch("/api/providers/fetch-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: provider.name, base_url: provider.base_url, key: keyVal.trim() || undefined }),
      })
      const data = await resp.json()
      if (data.models?.length) {
        setModels(prev => [...new Set([...prev, ...data.models])])
      }
    } catch {} finally { setFetching(false) }
  }

  const addModel = async (modelId: string) => {
    await fetch(`/api/providers/${provider.name}/models`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "add", model_id: modelId }),
    })
    setModels(prev => [...prev, modelId])
    setNewModel("")
  }

  const removeModel = async (modelId: string) => {
    await fetch(`/api/providers/${provider.name}/models`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "remove", model_id: modelId }),
    })
    setModels(prev => prev.filter(m => m !== modelId))
  }

  return (
    <div className="space-y-4 py-2">
      <h3 className="text-sm font-medium">{provider.display_name || provider.name}</h3>

      {/* API Key */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-muted-foreground">API Key</label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type={showKey ? "text" : "password"}
              placeholder={provider.has_key ? "•••••••• (set new value)" : "Enter API key"}
              value={keyVal}
              onChange={e => { setKeyVal(e.target.value); setConnStatus("idle") }}
              onKeyDown={e => { if (e.key === "Enter") handleSave() }}
              className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <button onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground/50 hover:text-foreground">
              {showKey ? "hide" : "show"}
            </button>
          </div>
          <button onClick={handleTest} disabled={testing} className="shrink-0 rounded-lg border border-border px-2.5 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-40 transition-all duration-200" title="Verify connection">
            {testing ? <Loader2 className="size-3.5 animate-spin" /> : <span className={connStatus === "ok" ? "text-green-500" : connStatus === "fail" ? "text-red-500" : "text-muted-foreground/50"}>🔗</span>}
          </button>
        </div>
      </div>

      {/* Base URL */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-muted-foreground">Base URL</label>
        <input
          type="text"
          value={provider.base_url || ""}
          readOnly
          className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground/70 cursor-default"
        />
      </div>

      <button onClick={handleSave} disabled={!keyVal.trim() || saving} className="w-full rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs font-medium hover:bg-primary/90 disabled:opacity-40 transition-all duration-200">
        {saving ? <Loader2 className="size-3.5 animate-spin mx-auto" /> : provider.has_key ? "Update Key" : "Save Key"}
      </button>

      {/* Models */}
      <div className="border-t border-border/50 pt-3 space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-medium text-muted-foreground">Models ({models.length})</label>
          <button onClick={handleFetchModels} disabled={fetching} className="text-[10px] text-muted-foreground hover:text-foreground transition-colors">
            {fetching ? <Loader2 className="size-3 animate-spin" /> : "Fetch from API"}
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {models.map(m => (
            <span key={m} className="inline-flex items-center gap-1 rounded-full bg-secondary/10 text-secondary-foreground px-2.5 py-0.5 text-xs group">
              {m}
              <button onClick={() => removeModel(m)} className="opacity-0 group-hover:opacity-100 text-[10px] hover:text-red-500 transition-all">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-1.5">
          <input
            type="text"
            placeholder="Add model ID..."
            value={newModel}
            onChange={e => setNewModel(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && newModel.trim()) addModel(newModel.trim()) }}
            className="flex-1 rounded-lg border border-border bg-background px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button onClick={() => newModel.trim() && addModel(newModel.trim())} disabled={!newModel.trim()} className="shrink-0 rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-muted/50 disabled:opacity-30 transition-all duration-200">
            Add
          </button>
        </div>
      </div>
    </div>
  )
}

function AddCustomOverlay({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!name.trim() || !url.trim()) return
    setSaving(true)
    try {
      await fetch("/api/providers/key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim().toLowerCase(), key: apiKey.trim() }),
      })
      onDone()
    } catch {} finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/20" onClick={onCancel}>
      <div className="w-[360px] rounded-xl bg-card border border-border shadow-xl p-5 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3">
          <button onClick={onCancel} className="text-muted-foreground hover:text-foreground text-sm">← Back</button>
          <span className="text-sm font-medium">Add Custom Provider</span>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-[11px] font-medium text-muted-foreground">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="my-provider" className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 mt-1" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-muted-foreground">Base URL</label>
            <input type="text" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://api.example.com/v1" className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 mt-1" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-muted-foreground">API Key</label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-..." className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 mt-1" />
          </div>
        </div>
        <button onClick={submit} disabled={!name.trim() || !url.trim() || saving} className="w-full rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs font-medium hover:bg-primary/90 disabled:opacity-40 transition-all duration-200">
          {saving ? <Loader2 className="size-3.5 animate-spin mx-auto" /> : "Add Provider"}
        </button>
      </div>
    </div>
  )
}

function ScenesTab({ data }: { data: TabData }) {
  const scenes = data?.scenes || []
  return (
    <div className="space-y-3 stagger-1">
      {scenes.map((s: { id: string; name?: string; kbs?: string[]; skills?: string[] }) => (
        <div key={s.id} className="rounded-xl border border-border/60 p-4 hover:shadow-sm transition-shadow duration-200">
          <h3 className="text-sm font-medium text-foreground mb-2">{s.name || s.id}</h3>
          <div className="flex gap-2 flex-wrap">
            {s.kbs?.map((kb: string) => (
              <span key={kb} className="rounded-full bg-secondary/10 text-secondary-foreground px-2.5 py-0.5 text-xs">{kb}</span>
            ))}
            {s.skills?.map((sk: string) => (
              <span key={sk} className="rounded-full bg-tertiary/10 text-tertiary-foreground px-2.5 py-0.5 text-xs">{sk}</span>
            ))}
          </div>
        </div>
      ))}
      {scenes.length === 0 && (
        <p className="text-sm text-muted-foreground/60">
          No scenes configured. Create scene.yaml files in the scenes/ directory.
        </p>
      )}
    </div>
  )
}

function SkillsTab({ data }: { data: TabData }) {
  const global = data?.global || []
  return (
    <div className="space-y-3 stagger-1">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Global Skills</h3>
      {global.map((s: { name: string; description: string }) => (
        <div key={s.name} className="rounded-xl border border-border/60 px-4 py-3 hover:shadow-sm transition-shadow duration-200">
          <span className="text-sm font-medium text-foreground">{s.name}</span>
          <p className="text-xs text-muted-foreground/70 mt-0.5">{s.description}</p>
        </div>
      ))}
      {global.length === 0 && (
        <p className="text-sm text-muted-foreground/60">No skills loaded. Add .md files to skills/public/.</p>
      )}
    </div>
  )
}

function KBTab({ data, onUpdate }: { data: TabData; onUpdate: () => void }) {
  const [uploading, setUploading] = useState(false)
  const kbs = data?.kbs || []

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append("file", file)
    const kbName = kbs[0]?.id || "default"
    await fetch(`/api/knowledge/${kbName}/upload`, { method: "POST", body: form })
    setUploading(false)
    onUpdate()
  }

  return (
    <div className="space-y-4 stagger-1">
      <div className="flex gap-2 overflow-x-auto pb-2">
{kbs.map((kb: { id: string; purpose?: string }) => (
          <button key={kb.id} className="shrink-0 rounded-full bg-secondary/10 text-secondary-foreground px-4 py-1.5 text-sm hover:bg-secondary/20 transition-all duration-200">
            {kb.id}
          </button>
        ))}
        <button className="shrink-0 rounded-full border border-dashed border-border px-4 py-1.5 text-sm text-muted-foreground/60 hover:text-foreground hover:border-foreground/30 transition-all duration-200">
          + New KB
        </button>
      </div>

      <div className="rounded-xl border-2 border-dashed border-border p-10 text-center hover:border-muted-foreground/30 transition-colors duration-200">
        <input type="file" id="kb-upload" className="hidden" onChange={handleUpload} disabled={uploading} />
        <label htmlFor="kb-upload" className="cursor-pointer">
          <p className="text-2xl text-muted-foreground/30 mb-2">
            {uploading ? <Loader2 className="inline size-5 animate-spin" /> : "📄"}
          </p>
          <p className="text-sm text-muted-foreground/60">
            {uploading ? "Uploading..." : "Click or drag files to upload"}
          </p>
        </label>
      </div>

      {kbs.map((kb: { id: string; purpose?: string }) => (
        <div key={kb.id} className="text-xs text-muted-foreground/60">
          <span className="font-medium text-foreground/80">{kb.id}</span>: {kb.purpose?.slice(0, 100)}
        </div>
      ))}
    </div>
  )
}

function ChannelsTab({ data }: { data: TabData }) {
  const channels = data?.channels || []
  return (
    <div className="space-y-2 stagger-1">
      {channels.map((ch: { channel_type: string; target_type: string; target_id: string; status: string }) => (
        <div key={`${ch.channel_type}-${ch.target_id}`} className="flex items-center justify-between rounded-xl border border-border/60 px-4 py-3 hover:shadow-sm transition-shadow duration-200">
          <div>
            <span className="text-sm font-medium text-foreground">{ch.channel_type}</span>
            <span className="text-xs text-muted-foreground/60 ml-2">
              → {ch.target_type}:{ch.target_id}
            </span>
          </div>
          <span className={`text-xs font-medium ${ch.status === "connected" ? "text-secondary" : "text-muted-foreground/50"}`}>
            {ch.status || "stopped"}
          </span>
        </div>
      ))}
      <p className="text-xs text-muted-foreground/50 pt-1">
        Connect channels via scene.yaml config or /api/channels/connect.
      </p>
    </div>
  )
}

function AppearanceTab() {
  const { theme, toggleTheme } = useTheme()
  const { lang, setLang } = useLang()

  return (
    <div className="space-y-5 stagger-1">
      {/* Theme */}
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Theme</h3>
        <div className="grid grid-cols-2 gap-3">
          {["light", "dark"].map(t => (
            <button
              key={t}
              onClick={() => { if (t !== theme) toggleTheme() }}
              className={`rounded-xl border-2 p-4 text-center transition-all duration-200 ${
                theme === t ? "border-primary bg-primary/5" : "border-border/60 hover:border-foreground/20"
              }`}
            >
              <div className="text-2xl mb-1">{t === "light" ? "☀️" : "🌙"}</div>
              <div className={`text-xs font-medium ${theme === t ? "text-primary" : "text-muted-foreground"}`}>
                {t === "light" ? "Light" : "Dark"}
              </div>
              {theme === t && <div className="text-[10px] text-primary mt-0.5">Active</div>}
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Language</h3>
        <div className="grid grid-cols-2 gap-3">
          {["en", "zh"].map(l => (
            <button
              key={l}
              onClick={() => setLang(l as "en" | "zh")}
              className={`rounded-xl border-2 p-4 text-center transition-all duration-200 ${
                lang === l ? "border-primary bg-primary/5" : "border-border/60 hover:border-foreground/20"
              }`}
            >
              <div className={`text-xs font-medium ${lang === l ? "text-primary" : "text-muted-foreground"}`}>
                {l === "en" ? "English" : "中文"}
              </div>
              {lang === l && <div className="text-[10px] text-primary mt-0.5">Active</div>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function GeneralTab() {
  return (
    <div className="space-y-4 stagger-1">
      <div className="rounded-xl border border-border/60 px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">Workspace</h3>
        <p className="text-xs text-muted-foreground/60 mt-0.5">workspace/</p>
      </div>
      <div className="rounded-xl border border-border/60 px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">Version</h3>
        <p className="text-xs text-muted-foreground/60 mt-0.5">CocoCat v2.0.0</p>
      </div>
    </div>
  )
}
