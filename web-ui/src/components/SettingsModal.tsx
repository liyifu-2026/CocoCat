import { useState, useEffect } from "react"
import { X, Loader2 } from "lucide-react"

const TABS = ["智能体", "供应商", "场景", "技能", "知识库", "渠道", "外观", "通用"]

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [tab, setTab] = useState(0)
  const [data, setData] = useState<any>({})

  useEffect(() => {
    if (!open) return
    // Load data based on tab
    const endpoints: Record<number, string> = {
      0: "/api/agents",
      1: "/api/providers",
      2: "/api/scenes",
      3: "/api/skills",
      4: "/api/knowledge",
      5: "/api/channels",
    }
    const url = endpoints[tab]
    if (url) fetch(url).then(r => r.json()).then(setData).catch(() => {})
  }, [tab, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="flex h-[600px] w-[800px] rounded-lg bg-background shadow-xl" onClick={e => e.stopPropagation()}>
        {/* Left nav */}
        <nav className="w-40 border-r p-3 space-y-1">
          {TABS.map((name, i) => (
            <button
              key={name}
              onClick={() => setTab(i)}
              className={`w-full rounded px-3 py-2 text-left text-sm ${
                tab === i ? "bg-blue-500 text-white" : "hover:bg-muted"
              }`}
            >
              {name}
            </button>
          ))}
        </nav>

        {/* Right content */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h2 className="font-bold">{TABS[tab]}</h2>
            <button onClick={onClose} className="hover:bg-muted rounded p-1">
              <X className="size-4" />
            </button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <SettingsContent tab={tab} data={data} onUpdate={() => {
              // Refresh data
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

function SettingsContent({ tab, data, onUpdate }: { tab: number; data: any; onUpdate: () => void }) {
  switch (tab) {
    case 0: return <AgentsTab data={data} />
    case 1: return <ProvidersTab data={data} />
    case 2: return <ScenesTab data={data} />
    case 3: return <SkillsTab data={data} />
    case 4: return <KBTab data={data} onUpdate={onUpdate} />
    case 5: return <ChannelsTab data={data} />
    case 6: return <AppearanceTab />
    case 7: return <GeneralTab />
    default: return null
  }
}

function AgentsTab({ data }: { data: any }) {
  const agents = data?.agents || []
  return (
    <div className="space-y-4">
      {agents.map((a: any) => (
        <div key={a.id} className="rounded border p-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium">{a.name}</h3>
              <p className="text-xs text-muted-foreground">ID: {a.id} · Role: {a.role} · Model: {a.model}</p>
            </div>
            <span className={`rounded px-2 py-0.5 text-xs ${
              a.status === "running" ? "bg-green-100 text-green-700" : "bg-muted"
            }`}>
              {a.status || "stopped"}
            </span>
          </div>
        </div>
      ))}
      <p className="text-xs text-muted-foreground">
        Agent management via admin panel. Main AI always present.
      </p>
    </div>
  )
}

function ProvidersTab({ data }: { data: any }) {
  const providers = data?.providers || []
  return (
    <div className="space-y-3">
      {providers.map((p: any) => (
        <div key={p.name} className="flex items-center justify-between rounded border px-3 py-2">
          <div>
            <span className="font-medium">{p.display_name}</span>
            <span className="text-xs text-muted-foreground ml-2">({p.name})</span>
          </div>
          <span className={`text-xs ${p.has_key ? "text-green-600" : "text-muted-foreground"}`}>
            {p.has_key ? "✓ Key configured" : "No key"}
          </span>
        </div>
      ))}
      <p className="text-xs text-muted-foreground mt-2">
        Configure API keys in config/auth.json or via environment variables.
      </p>
    </div>
  )
}

function ScenesTab({ data }: { data: any }) {
  const scenes = data?.scenes || []
  return (
    <div className="space-y-3">
      {scenes.map((s: any) => (
        <div key={s.id} className="rounded border p-3">
          <h3 className="font-medium">{s.name || s.id}</h3>
          <div className="flex gap-2 mt-1">
            {s.kbs?.map((kb: string) => (
              <span key={kb} className="rounded bg-muted px-2 py-0.5 text-xs">📚 {kb}</span>
            ))}
            {s.skills?.map((sk: string) => (
              <span key={sk} className="rounded bg-muted px-2 py-0.5 text-xs">🔧 {sk}</span>
            ))}
          </div>
        </div>
      ))}
      {scenes.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No scenes configured. Create scene.yaml files in the scenes/ directory.
        </p>
      )}
    </div>
  )
}

function SkillsTab({ data }: { data: any }) {
  const global = data?.global || []
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">Global Skills</h3>
      {global.map((s: any) => (
        <div key={s.name} className="rounded border px-3 py-2">
          <span className="font-medium">{s.name}</span>
          <p className="text-xs text-muted-foreground">{s.description}</p>
        </div>
      ))}
      {global.length === 0 && (
        <p className="text-sm text-muted-foreground">No skills loaded. Add .md files to skills/public/.</p>
      )}
    </div>
  )
}

function KBTab({ data, onUpdate }: { data: any; onUpdate: () => void }) {
  const [uploading, setUploading] = useState(false)
  const kbs = data?.kbs || []

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append("file", file)
    // Upload to first KB (or let user select)
    const kbName = kbs[0]?.id || "default"
    await fetch(`/api/knowledge/${kbName}/upload`, { method: "POST", body: form })
    setUploading(false)
    onUpdate()
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 overflow-x-auto pb-2">
        {kbs.map((kb: any) => (
          <button key={kb.id} className="flex-shrink-0 rounded-full bg-muted px-4 py-2 text-sm hover:bg-accent">
            {kb.id}
          </button>
        ))}
        <button className="flex-shrink-0 rounded-full border border-dashed px-4 py-2 text-sm text-muted-foreground hover:bg-muted">
          + New KB
        </button>
      </div>

      <div className="rounded border-2 border-dashed p-8 text-center">
        <input type="file" id="kb-upload" className="hidden" onChange={handleUpload} disabled={uploading} />
        <label htmlFor="kb-upload" className="cursor-pointer">
          <p className="text-muted-foreground">
            {uploading ? <Loader2 className="inline size-4 animate-spin" /> : "📂"}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {uploading ? "Uploading..." : "Click or drag files to upload"}
          </p>
        </label>
      </div>

      {kbs.map((kb: any) => (
        <div key={kb.id} className="text-xs text-muted-foreground">
          <span className="font-medium">{kb.id}</span>: {kb.purpose?.slice(0, 100)}
        </div>
      ))}
    </div>
  )
}

function ChannelsTab({ data }: { data: any }) {
  const channels = data?.channels || []
  return (
    <div className="space-y-3">
      {channels.map((ch: any, i: number) => (
        <div key={i} className="flex items-center justify-between rounded border px-3 py-2">
          <div>
            <span className="font-medium">{ch.channel_type}</span>
            <span className="text-xs text-muted-foreground ml-2">
              → {ch.target_type}:{ch.target_id}
            </span>
          </div>
          <span className={`text-xs ${ch.status === "connected" ? "text-green-600" : "text-muted-foreground"}`}>
            {ch.status || "stopped"}
          </span>
        </div>
      ))}
      <p className="text-xs text-muted-foreground">
        Connect channels via scene.yaml config or /api/channels/connect.
      </p>
    </div>
  )
}

function AppearanceTab() {
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-3">
        <span className="text-sm">Theme</span>
        <select className="rounded border px-2 py-1 text-sm">
          <option>System</option>
          <option>Light</option>
          <option>Dark</option>
        </select>
      </label>
    </div>
  )
}

function GeneralTab() {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium">Workspace</h3>
        <p className="text-xs text-muted-foreground">workspace/</p>
      </div>
      <div>
        <h3 className="text-sm font-medium">Version</h3>
        <p className="text-xs text-muted-foreground">CocoCat v2.0.0</p>
      </div>
    </div>
  )
}
