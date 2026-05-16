import { useState, useEffect, useRef } from "react"
import { ChevronLeft, ChevronRight, Loader2, RotateCcw, Save, Zap, ChevronDown } from "lucide-react"
import type { TabData } from "@/types/settings"
import { PROVIDER_ICONS } from "@/lib/provider-icons"

const ROLES = [
  { key: "coco", name: "Coco", tagline: "协调者", emoji: "🧠" },
  { key: "worker", name: "子代理", tagline: "执行者 × N", emoji: "🛠️" },
] as const

type RoleKey = (typeof ROLES)[number]["key"]

interface ProviderGroup {
  name: string
  display_name: string
  models: string[]
}

function logoLetters(name: string): string {
  return name.replace(/[^a-zA-Z]/g, "").slice(0, 2).toUpperCase()
}

// Color palette (moved from ProvidersTab)
const LOGO_COLORS = [
  "bg-blue-100 text-blue-600", "bg-emerald-100 text-emerald-600", "bg-orange-100 text-orange-600",
  "bg-purple-100 text-purple-600", "bg-cyan-100 text-cyan-600", "bg-rose-100 text-rose-600",
  "bg-amber-100 text-amber-600", "bg-lime-100 text-lime-600", "bg-teal-100 text-teal-600",
  "bg-indigo-100 text-indigo-600", "bg-pink-100 text-pink-600", "bg-sky-100 text-sky-600",
  "bg-fuchsia-100 text-fuchsia-600", "bg-green-100 text-green-600",
]

function localLogoColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return LOGO_COLORS[Math.abs(hash) % LOGO_COLORS.length]!
}

export function AgentsTab({ data }: { data: TabData }) {
  const [role, setRole] = useState<RoleKey>("coco")
  const [providers, setProviders] = useState<ProviderGroup[]>([])
  const [cocoModel, setCocoModel] = useState("")
  const [workerModel, setWorkerModel] = useState("deepseek-chat")
  const [prompt, setPrompt] = useState("")
  const [defaultPrompt, setDefaultPrompt] = useState("")
  const [isCustomPrompt, setIsCustomPrompt] = useState(false)
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [savingModel, setSavingModel] = useState(false)
  const [savingWorker, setSavingWorker] = useState(false)
  const [promptDirty, setPromptDirty] = useState(false)

  // Load enabled models grouped by provider
  useEffect(() => {
    fetch("/api/models/enabled").then(r => r.json()).then(d => {
      const groups: ProviderGroup[] = []
      for (const [name, info] of Object.entries(d.providers || {}) as [string, { display_name: string; models: string[] }][]) {
        if (info.models?.length > 0) {
          groups.push({ name, display_name: info.display_name, models: info.models })
        }
      }
      setProviders(groups)
    }).catch(() => {})
  }, [])

  // Load Coco prompt + model
  useEffect(() => {
    fetch("/api/agents/main/prompt").then(r => r.json()).then(d => {
      setPrompt(d.prompt || "")
      setDefaultPrompt(d.default || "")
      setIsCustomPrompt(d.is_custom || false)
    }).catch(() => {})

    fetch("/api/agents/main").then(r => r.json()).then(d => {
      if (d.model) setCocoModel(d.model)
    }).catch(() => {})
  }, [])

  // Load worker config
  useEffect(() => {
    fetch("/api/agents/config").then(r => r.json()).then(d => {
      if (d.worker_model) setWorkerModel(d.worker_model)
    }).catch(() => {})
  }, [])

  const handleSavePrompt = async () => {
    if (!prompt.trim()) return
    setSavingPrompt(true)
    await fetch("/api/agents/main/prompt", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt.trim() }),
    })
    setIsCustomPrompt(true)
    setPromptDirty(false)
    setSavingPrompt(false)
  }

  const handleResetPrompt = async () => {
    setSavingPrompt(true)
    await fetch("/api/agents/main/prompt", { method: "DELETE" })
    setPrompt(defaultPrompt)
    setIsCustomPrompt(false)
    setPromptDirty(false)
    setSavingPrompt(false)
  }

  const handleSaveCocoModel = async (model: string) => {
    setCocoModel(model)
    setSavingModel(true)
    await fetch("/api/agents/main", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    })
    setSavingModel(false)
  }

  const handleSaveWorkerModel = async (model: string) => {
    setWorkerModel(model)
    setSavingWorker(true)
    await fetch("/api/agents/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    })
    setSavingWorker(false)
  }

  const current = ROLES.find(r => r.key === role)!
  const idx = ROLES.findIndex(r => r.key === role)
  const prev = idx > 0 ? ROLES[idx - 1]! : ROLES[ROLES.length - 1]!
  const next = idx < ROLES.length - 1 ? ROLES[idx + 1]! : ROLES[0]!

  return (
    <div className="flex flex-col items-center py-6 gap-6">
      {/* ── Character Card with arrows ── */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => setRole(prev.key)}
          className="size-8 rounded-full border border-border bg-card hover:bg-accent hover:border-foreground/20 flex items-center justify-center text-muted-foreground hover:text-foreground transition-all duration-200 active:scale-90"
        >
          <ChevronLeft className="size-4" />
        </button>

        <div className="w-[200px] rounded-3xl border-2 border-border/60 bg-card p-5 text-center shadow-sm hover:shadow-md transition-all duration-300">
          <div className="text-5xl mb-2 animate-in">{current.emoji}</div>
          <div className="text-base font-bold text-foreground tracking-tight">{current.name}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">{current.tagline}</div>
        </div>

        <button
          onClick={() => setRole(next.key)}
          className="size-8 rounded-full border border-border bg-card hover:bg-accent hover:border-foreground/20 flex items-center justify-center text-muted-foreground hover:text-foreground transition-all duration-200 active:scale-90"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      {/* ── Config slots ── */}
      <div className="w-full space-y-4">
        <Slot label="核心引擎">
          <div className="flex items-center gap-2">
            <Zap className="size-3.5 text-amber-500 shrink-0" />
            <span className="text-[11px] text-muted-foreground shrink-0">
              {role === "coco" ? "LLM 模型" : "默认模型"}
            </span>
            <ModelSelect
              providers={providers}
              value={role === "coco" ? cocoModel : workerModel}
              onChange={role === "coco" ? handleSaveCocoModel : handleSaveWorkerModel}
            />
            {(savingModel || savingWorker) && <Loader2 className="size-3 animate-spin text-muted-foreground shrink-0" />}
          </div>
          {role === "worker" && (
            <p className="text-[10px] text-muted-foreground/60 mt-2 px-1">子代理按需创建，任务完成后自动销毁。此处设置所有子代理的默认模型。</p>
          )}
        </Slot>

        {/* Mind Nexus — Coco only */}
        {role === "coco" && (
          <Slot label="思维中枢">
            <div className="relative">
              <textarea
                value={prompt}
                onChange={e => { setPrompt(e.target.value); setPromptDirty(true) }}
                className="w-full min-h-[200px] rounded-lg border border-border bg-background px-3 py-2.5 text-xs font-mono text-foreground/80 leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                placeholder="System prompt..."
                spellCheck={false}
              />
              {isCustomPrompt && (
                <span className="absolute top-2 right-2 text-[9px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-600 font-medium">自定义</span>
              )}
            </div>
            <div className="flex justify-end gap-2 mt-2">
              {isCustomPrompt && (
                <button
                  onClick={handleResetPrompt}
                  disabled={savingPrompt}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-all duration-200 disabled:opacity-40"
                >
                  <RotateCcw className="size-3" />
                  恢复默认
                </button>
              )}
              <button
                onClick={handleSavePrompt}
                disabled={!promptDirty || savingPrompt}
                className="flex items-center gap-1 rounded-lg bg-violet-600 text-white px-4 py-1.5 text-xs font-medium hover:bg-violet-700 disabled:opacity-40 transition-all duration-200 active:scale-95"
              >
                {savingPrompt ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />}
                保存
              </button>
            </div>
          </Slot>
        )}
      </div>
    </div>
  )
}

function ModelSelect({ providers, value, onChange }: { providers: ProviderGroup[]; value: string; onChange: (m: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  // Find current display
  let currentDisplay = value
  let currentProvider = ""
  for (const p of providers) {
    if (p.models.includes(value)) { currentProvider = p.display_name; break }
  }

  return (
    <div className="relative flex-1" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2 text-xs text-left hover:border-foreground/20 transition-colors"
      >
        <span className="font-medium text-foreground truncate flex-1">{currentDisplay}</span>
        {currentProvider && (
          <span className="text-[9px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded font-medium shrink-0">{currentProvider}</span>
        )}
        <ChevronDown className={`size-3 text-muted-foreground shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 z-30 rounded-xl border border-border bg-card shadow-xl overflow-hidden max-h-[280px] overflow-y-auto">
          {providers.map(p => (
            <div key={p.name}>
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-muted/30">
                {(() => {
                  const Icon = PROVIDER_ICONS[p.name]
                  return Icon ? <Icon size={14} /> : <span className="size-4 rounded flex items-center justify-center text-[8px] font-bold shrink-0 bg-slate-100 text-slate-500">{logoLetters(p.display_name || p.name)}</span>
                })()}
                <span className="text-[10px] font-medium text-muted-foreground uppercase">{p.display_name}</span>
              </div>
              {p.models.map(m => (
                <button
                  key={m}
                  onClick={() => { onChange(m); setOpen(false) }}
                  className={`w-full text-left px-6 py-1.5 text-xs hover:bg-accent transition-colors ${m === value ? "bg-accent text-foreground font-medium" : "text-muted-foreground"}`}
                >
                  {m}
                </button>
              ))}
            </div>
          ))}
          {providers.length === 0 && (
            <div className="px-4 py-6 text-xs text-muted-foreground/50 text-center">
              暂无已启用模型。<br />
              <span className="text-[10px]">请在 设置 → 供应商 中配置。</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Slot({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-card/50 p-4">
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-3">{label}</div>
      {children}
    </div>
  )
}
