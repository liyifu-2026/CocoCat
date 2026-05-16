import { useTheme } from "@/context/ThemeContext"
import { useLang } from "@/context/LanguageContext"
export function AppearanceTab() {
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
