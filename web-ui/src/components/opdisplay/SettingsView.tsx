import { useTheme } from "@/context/ThemeContext"
import { useLang } from "@/context/LanguageContext"

export default function SettingsView() {
  const { theme, toggleTheme } = useTheme()
  const { lang, setLang } = useLang()

  return (
    <div className="p-4 space-y-2.5">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-3">⚙ Settings</div>
        <div className="space-y-2">
          <div className="flex items-center justify-between py-1.5">
            <span className="text-[10px] text-foreground">Theme</span>
            <button
              onClick={toggleTheme}
              className="text-[9px] px-2.5 py-1 rounded-full bg-muted border border-border text-muted-foreground"
            >
              {theme === "dark" ? "🌙 Dark" : "☀️ Light"}
            </button>
          </div>
          <div className="flex items-center justify-between py-1.5">
            <span className="text-[10px] text-foreground">Language</span>
            <select
              value={lang}
              onChange={e => setLang(e.target.value as "en" | "zh")}
              className="text-[9px] px-2 py-1 rounded-full bg-muted border border-border text-muted-foreground outline-none"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
