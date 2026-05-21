import { MessageSquare, Folder, BookOpen, Brain, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"

interface LeftNavProps {
  active: string
  onNavigate: (nav: string) => void
}

const NAV_ITEMS = [
  { key: "chat", icon: MessageSquare, labelKey: "nav.chat" },
  { key: "scenes", icon: Folder, labelKey: "nav.scenes" },
  { key: "knowledge", icon: BookOpen, labelKey: "nav.knowledge" },
  { key: "memory", icon: Brain, labelKey: "nav.memory" },
  { key: "settings", icon: Settings, labelKey: "nav.settings" },
] as const

export default function LeftNav({ active, onNavigate }: LeftNavProps) {
  const t = useT()

  return (
    <aside className="w-[76px] bg-sidebar border-r border-sidebar-border flex flex-col items-center shrink-0 py-5 gap-3.5">
      <div
        className="w-11 h-11 bg-card border border-border rounded-2xl flex items-center justify-center cursor-pointer hover:border-primary/30 transition-colors"
        onClick={() => onNavigate("chat")}
      >
        <span className="text-xs font-bold text-primary tracking-widest">CC</span>
      </div>

      <div className="w-8 h-px bg-border/50" />

      {NAV_ITEMS.map(({ key, icon: Icon, labelKey }) => (
        <button
          key={key}
          className={cn(
            "w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 relative group",
            active === key
              ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25"
              : "text-muted-foreground hover:bg-card hover:text-foreground"
          )}
          onClick={() => onNavigate(key)}
        >
          <Icon className="size-5" />
          <span className="absolute left-14 bg-popover text-muted-foreground text-[9px] px-2 py-1 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg border border-border">
            {t(labelKey)}
          </span>
        </button>
      ))}

      <div className="mt-auto w-9 h-9 rounded-full bg-muted border-2 border-emerald-500/30" />
    </aside>
  )
}
