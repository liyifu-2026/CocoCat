import { useState } from "react"
import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"

const MODE_STYLES = {
  default: {
    icon: "💬",
    titleKey: "chat.empty_title",
    subtitleKey: "mode.default",
    statusKey: "mode.default_status",
    bannerGradient: "from-blue-600 via-blue-500 to-indigo-500",
    avatarGradient: "from-blue-500 to-blue-300",
  },
  "kb-admin": {
    icon: "📚",
    titleKey: "mode.kb-admin",
    subtitleKey: "mode.kb_admin_subtitle",
    statusKey: "mode.kb_admin_status",
    bannerGradient: "from-amber-600 via-amber-500 to-orange-500",
    avatarGradient: "from-amber-500 to-amber-300",
  },
} as const

type ModeKey = keyof typeof MODE_STYLES

export default function Namecard() {
  const { currentMode, modes, setMode } = useMode()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const t = useT()

  const style = MODE_STYLES[(currentMode in MODE_STYLES ? currentMode : "default") as ModeKey]

  return (
    <div className="flex-shrink-0 animate-view-enter">
      {/* ── Hero Banner ── */}
      <div className={cn("relative overflow-hidden h-40", "bg-gradient-to-br", style.bannerGradient)}>
        {/* Radial glow accent */}
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/4 w-32 h-32 bg-white/5 rounded-full blur-2xl pointer-events-none" />

        {/* Wave SVG at bottom of banner */}
        <svg className="absolute bottom-0 left-0 w-full h-20 pointer-events-none" viewBox="0 0 1200 120" preserveAspectRatio="none">
          <path d="M0,60 C200,110 400,10 600,60 C800,110 1000,10 1200,60 L1200,120 L0,120 Z" fill="var(--background)" opacity="0.25" />
          <path d="M0,80 C300,30 500,110 700,70 C900,30 1100,100 1200,70 L1200,120 L0,120 Z" fill="var(--background)" opacity="0.12" />
        </svg>

        <div className="relative z-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4 px-5 h-full pb-4">
          <div className="flex items-end gap-4 self-end">
            <div className={cn(
              "w-20 h-20 rounded-full flex items-center justify-center text-3xl border-[3px] shadow-xl shrink-0",
              currentMode === "kb-admin" ? "bg-amber-100 border-amber-300" : "bg-blue-100 border-blue-300"
            )}>
              {style.icon}
            </div>
            <div className="pb-1 space-y-0.5">
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-wide">{t(style.titleKey)}</h1>
                <div className="relative">
                  <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="text-[10px] px-2.5 py-0.5 rounded-full font-medium cursor-pointer transition-colors flex items-center gap-1 bg-white/15 text-white"
                  >
                    {currentMode} <ChevronDown className="size-3" />
                  </button>
                  {dropdownOpen && (
                    <div className="absolute top-full left-0 mt-1 bg-popover border border-border rounded-lg py-1 shadow-lg z-20 min-w-[130px]">
                      {modes.map(m => (
                        <button
                          key={m.id}
                          onClick={() => { setMode(m.id); setDropdownOpen(false) }}
                          className={cn(
                            "w-full text-left px-3 py-1.5 text-[10px] rounded-md transition-colors",
                            m.id === currentMode ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-card"
                          )}
                        >
                          {m.name}
                        </button>
                      ))}
                    </div>
                  )}
                  {dropdownOpen && <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />}
                </div>
              </div>
              <p className="text-xs text-white/70">{t(style.subtitleKey)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Intro Quote ── */}
      <div className="px-5 py-4">
        <p className={cn(
          "text-[11px] italic text-muted-foreground border-l-2 pl-3",
          currentMode === "kb-admin" ? "border-amber-400/40" : "border-primary/40"
        )}>
          {t(style.statusKey)}
        </p>
      </div>
    </div>
  )
}
