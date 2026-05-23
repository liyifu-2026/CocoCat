import { useState, useEffect, lazy, Suspense } from "react"
import { Settings, Plug, Layers, Wrench, Book, Radio, Users, Pin, Palette } from "lucide-react"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"
import { Skeleton } from "@/components/ui/skeleton"
import type { TabData } from "@/types/settings"

const ProvidersTab = lazy(() => import("@/components/settings/ProvidersTab").then(m => ({ default: m.ProvidersTab })))
const ScenesTab = lazy(() => import("@/components/settings/ScenesTab").then(m => ({ default: m.ScenesTab })))
const SkillsTab = lazy(() => import("@/components/settings/SkillsTab").then(m => ({ default: m.SkillsTab })))
const KBTab = lazy(() => import("@/components/settings/KBTab").then(m => ({ default: m.KBTab })))
const ChannelsTab = lazy(() => import("@/components/settings/ChannelsTab").then(m => ({ default: m.ChannelsTab })))
const UsersTab = lazy(() => import("@/components/settings/UsersTab").then(m => ({ default: m.UsersTab })))
const PinnedTab = lazy(() => import("@/components/settings/PinnedTab").then(m => ({ default: m.PinnedTab })))
const AppearanceTab = lazy(() => import("@/components/settings/AppearanceTab").then(m => ({ default: m.AppearanceTab })))
const GeneralTab = lazy(() => import("@/components/settings/GeneralTab").then(m => ({ default: m.GeneralTab })))

const TABS = [
  { key: "providers", labelKey: "settings.tab.providers", icon: Plug, endpoint: "/api/providers" },
  { key: "scenes", labelKey: "settings.tab.scenes", icon: Layers, endpoint: "/api/scenes" },
  { key: "skills", labelKey: "settings.tab.skills", icon: Wrench, endpoint: "/api/skills" },
  { key: "kb", labelKey: "settings.tab.kb", icon: Book, endpoint: "/api/knowledge" },
  { key: "channels", labelKey: "settings.tab.channels", icon: Radio },
  { key: "users", labelKey: "settings.tab.users", icon: Users, endpoint: "/api/settings" },
  { key: "pinned", labelKey: "settings.tab.pinned", icon: Pin },
  { key: "appearance", labelKey: "settings.tab.appearance", icon: Palette },
  { key: "general", labelKey: "settings.tab.general", icon: Settings, endpoint: "/api/settings" },
]

function TabSkeleton() {
  return (
    <div className="p-5 space-y-4">
      <Skeleton className="h-6 w-32 rounded shimmer-skeleton" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl shimmer-skeleton" />
        ))}
      </div>
    </div>
  )
}

export default function SettingsView() {
  const [tab, setTab] = useState("providers")
  const [tabData, setTabData] = useState<TabData>({} as TabData)
  const t = useT()

  const loadTabData = (tabKey: string) => {
    const tabInfo = TABS.find(item => item.key === tabKey)
    if (tabInfo?.endpoint) {
      fetch(tabInfo.endpoint)
        .then(r => r.json())
        .then(d => setTabData(d))
        .catch(() => {})
    } else {
      setTabData({} as TabData)
    }
  }

  useEffect(() => { loadTabData(tab) }, [tab])

  const refresh = () => loadTabData(tab)

  return (
    <div className="flex h-full animate-view-enter">
      <div className="w-[150px] border-r border-sidebar-border bg-sidebar/30 p-2.5 flex flex-col gap-1 shrink-0">
        {TABS.map(item => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] transition-all text-left",
              tab === item.key
                ? "bg-tertiary text-tertiary-foreground font-medium"
                : "text-muted-foreground hover:bg-card"
            )}
          >
            <item.icon className="size-4 shrink-0" />
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<TabSkeleton />}>
          {tab === "providers" && <ProvidersTab key="providers" data={tabData} onUpdate={refresh} />}
          {tab === "scenes" && <ScenesTab key="scenes" data={tabData} />}
          {tab === "skills" && <SkillsTab key="skills" data={tabData} />}
          {tab === "kb" && <KBTab key="kb" data={tabData} onUpdate={refresh} />}
          {tab === "channels" && <ChannelsTab key="channels" />}
          {tab === "users" && <UsersTab key="users" />}
          {tab === "pinned" && <PinnedTab key="pinned" />}
          {tab === "appearance" && <AppearanceTab key="appearance" />}
          {tab === "general" && <GeneralTab key="general" data={tabData} onUpdate={refresh} />}
        </Suspense>
      </div>
    </div>
  )
}
