import { useState } from "react"
import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"

const MODE_STYLES = {
  default: {
    icon: "💬",
    titleKey: "chat.empty_title",
    subtitleKey: "mode.default",
    statusKey: "mode.default_status",
    gradient: "bg-gradient-to-b from-blue-500/10 to-transparent",
  },
  "kb-admin": {
    icon: "📚",
    titleKey: "mode.kb-admin",
    subtitleKey: "mode.kb_admin_subtitle",
    statusKey: "mode.kb_admin_status",
    gradient: "bg-gradient-to-b from-amber-500/10 to-transparent",
  },
} as const

type ModeKey = keyof typeof MODE_STYLES

export default function Namecard() {
  const { currentMode, modes, setMode } = useMode()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const t = useT()

  const style = MODE_STYLES[(currentMode in MODE_STYLES ? currentMode : "default") as ModeKey]

  return (
    <div className={cn("px-6 py-6 text-center border-b border-border flex-shrink-0 relative", style.gradient)}>
      <div className={cn(
        "w-14 h-14 mx-auto mb-2.5 rounded-full flex items-center justify-center text-2xl border-2",
        currentMode === "kb-admin" ? "bg-amber-500/10 border-amber-500/25" : "bg-blue-500/10 border-blue-500/25"
      )}>
        {style.icon}
      </div>

      <h2 className="text-[15px] font-semibold text-foreground">{t(style.titleKey)}</h2>
      <p className="text-[10px] text-muted-foreground mt-0.5">{t(style.subtitleKey)}</p>

      <div className="relative inline-block mt-2">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className={cn(
            "text-[10px] px-3 py-1 rounded-full font-medium cursor-pointer transition-colors",
            currentMode === "kb-admin"
              ? "bg-amber-500/12 text-amber-400"
              : "bg-primary/12 text-primary"
          )}
        >
          {currentMode} ▾
        </button>

        {dropdownOpen && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 bg-popover border border-border rounded-lg py-1 shadow-lg z-20 min-w-[130px]">
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
      </div>

      <p className="text-[10px] text-muted-foreground/70 italic mt-1.5">{t(style.statusKey)}</p>

      {dropdownOpen && <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />}
    </div>
  )
}
