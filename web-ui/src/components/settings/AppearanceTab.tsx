import { useTheme } from "@/context/ThemeContext"
import { useLang, useT } from "@/context/LanguageContext"
export function AppearanceTab() {
  const { theme, toggleTheme } = useTheme()
  const { lang, setLang } = useLang()
  const t = useT()

  return (
    <div className="space-y-5 stagger-1">
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">{t("settings.theme_label")}</h3>
        <div className="grid grid-cols-2 gap-3">
          {["light", "dark"].map(mode => (
            <button
              key={mode}
              onClick={() => { if (mode !== theme) toggleTheme() }}
              className={`rounded-xl border-2 p-4 text-center transition-all duration-200 ${
                theme === mode ? "border-primary bg-primary/5" : "border-border/60 hover:border-foreground/20"
              }`}
            >
              <div className="text-2xl mb-1">{mode === "light" ? "☀️" : "🌙"}</div>
              <div className={`text-xs font-medium ${theme === mode ? "text-primary" : "text-muted-foreground"}`}>
                {t(mode === "light" ? "settings.light" : "settings.dark")}
              </div>
              {theme === mode && <div className="text-[10px] text-primary mt-0.5">{t("settings.active")}</div>}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">{t("settings.language_label")}</h3>
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
                {l === "en" ? t("settings.english") : t("settings.chinese")}
              </div>
              {lang === l && <div className="text-[10px] text-primary mt-0.5">{t("settings.active")}</div>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
