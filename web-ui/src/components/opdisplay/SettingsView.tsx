import { useState } from "react"
import { Settings, Plug, Layers, Wrench, Book, Radio, Users, Pin, Palette } from "lucide-react"
import { cn } from "@/lib/utils"
import { ProvidersTab } from "@/components/settings/ProvidersTab"
import { ScenesTab } from "@/components/settings/ScenesTab"
import { SkillsTab } from "@/components/settings/SkillsTab"
import { KBTab } from "@/components/settings/KBTab"
import { ChannelsTab } from "@/components/settings/ChannelsTab"
import { UsersTab } from "@/components/settings/UsersTab"
import { PinnedTab } from "@/components/settings/PinnedTab"
import { AppearanceTab } from "@/components/settings/AppearanceTab"
import { GeneralTab } from "@/components/settings/GeneralTab"
import type { TabData } from "@/types/settings"

const TABS = [
  { key: "providers", label: "Providers", icon: Plug },
  { key: "scenes", label: "Scenes", icon: Layers },
  { key: "skills", label: "Skills", icon: Wrench },
  { key: "kb", label: "KB", icon: Book },
  { key: "channels", label: "Channels", icon: Radio },
  { key: "users", label: "Users", icon: Users },
  { key: "pinned", label: "Pinned", icon: Pin },
  { key: "appearance", label: "Appearance", icon: Palette },
  { key: "general", label: "General", icon: Settings },
]

export default function SettingsView() {
  const [tab, setTab] = useState("providers")
  const [updateKey, setUpdateKey] = useState(0)
  const [tabData] = useState<TabData>({} as TabData)

  const refresh = () => setUpdateKey(k => k + 1)

  return (
    <div className="flex h-full">
      <div className="w-[150px] border-r border-sidebar-border bg-sidebar/30 p-2.5 flex flex-col gap-1 shrink-0">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] transition-all text-left",
              tab === t.key
                ? "bg-tertiary text-tertiary-foreground font-medium"
                : "text-muted-foreground hover:bg-card"
            )}
          >
            <t.icon className="size-4 shrink-0" />
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        {tab === "providers" && <ProvidersTab key={updateKey} data={tabData} onUpdate={refresh} />}
        {tab === "scenes" && <ScenesTab data={tabData} />}
        {tab === "skills" && <SkillsTab data={tabData} />}
        {tab === "kb" && <KBTab key={updateKey} data={tabData} onUpdate={refresh} />}
        {tab === "channels" && <ChannelsTab />}
        {tab === "users" && <UsersTab />}
        {tab === "pinned" && <PinnedTab />}
        {tab === "appearance" && <AppearanceTab />}
        {tab === "general" && <GeneralTab />}
      </div>
    </div>
  )
}
