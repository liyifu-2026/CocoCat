import { useState, useEffect, useRef } from "react"
import { X } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import type { TabItem, TabData, SettingsModalProps } from "@/types/settings"
import { AgentsTab } from "@/components/settings/AgentsTab"
import { ProvidersTab } from "@/components/settings/ProvidersTab"
import { ScenesTab } from "@/components/settings/ScenesTab"
import { SkillsTab } from "@/components/settings/SkillsTab"
import { KBTab } from "@/components/settings/KBTab"
import { ChannelsTab } from "@/components/settings/ChannelsTab"
import { UsersTab } from "@/components/settings/UsersTab"
import { PinnedTab } from "@/components/settings/PinnedTab"
import { AppearanceTab } from "@/components/settings/AppearanceTab"
import { GeneralTab } from "@/components/settings/GeneralTab"
import { Cpu, Plug, Layers, Wrench, Book, Radio, Users, Pin, Palette, Settings } from "lucide-react"

const TABS: TabItem[] = [
  { label: "智能体", icon: Cpu },
  { label: "供应商", icon: Plug },
  { label: "场景", icon: Layers },
  { label: "技能", icon: Wrench },
  { label: "知识库", icon: Book },
  { label: "渠道", icon: Radio },
  { label: "用户", icon: Users },
  { label: "钉选", icon: Pin },
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

function SettingsContent({ tab, data, onUpdate }: { tab: number; data: TabData; onUpdate: () => void }) {
  switch (tab) {
    case 0: return <AgentsTab data={data} />
    case 1: return <ProvidersTab data={data} onUpdate={onUpdate} />
    case 2: return <ScenesTab data={data} />
    case 3: return <SkillsTab data={data} />
    case 4: return <KBTab data={data} onUpdate={onUpdate} />
    case 5: return <ChannelsTab />
    case 6: return <UsersTab />
    case 7: return <PinnedTab />
    case 8: return <AppearanceTab />
    case 9: return <GeneralTab data={data} onUpdate={onUpdate} />
    default: return null
  }
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
      7: "/api/settings",
    }
    const url = endpoints[tab]
    if (url) fetch(url, { signal: abort.signal }).then(r => r.json()).then(d => { if (!abort.signal.aborted) setData(d) }).catch(() => {})
    return () => abort.abort()
  }, [tab, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-[680px] max-w-[960px] w-[95vw] rounded-2xl bg-card shadow-2xl border border-border/50 overflow-hidden animate-in"
        onClick={e => e.stopPropagation()}
        style={{ animation: "fadeSlideUp 0.2s ease-out both" }}
      >
        {/* Left nav */}
        <nav className="w-52 border-r border-border bg-muted/30 p-3 space-y-1">
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
                4: "/api/knowledge", 7: "/api/settings",
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
