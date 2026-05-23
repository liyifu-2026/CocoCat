import { useState, useEffect } from "react"
import { Folder, Pencil, X, Check, FolderOpen, Key, Repeat } from "lucide-react"
import { useT } from "@/context/LanguageContext"

interface GeneralTabProps {
  data?: { workspace?: string; keys?: { name: string; label: string; has_key: boolean }[]; max_iterations?: number }
  onUpdate?: () => void
}

export function GeneralTab({ data, onUpdate }: GeneralTabProps) {
  const t = useT()
  const [value, setValue] = useState("")
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")

  const [tavilyKey, setTavilyKey] = useState("")
  const [tavilyEditing, setTavilyEditing] = useState(false)
  const [tavilySaving, setTavilySaving] = useState(false)
  const [tavilyMsg, setTavilyMsg] = useState("")
  const tavilyHasKey = data?.keys?.find(k => k.name === "tavily")?.has_key ?? false

  const [maxIter, setMaxIter] = useState(data?.max_iterations ?? 30)
  const [maxIterEditing, setMaxIterEditing] = useState(false)
  const [maxIterSaving, setMaxIterSaving] = useState(false)

  useEffect(() => {
    if (data?.workspace && !value) setValue(data.workspace)
  }, [data?.workspace])

  useEffect(() => {
    if (data?.max_iterations) setMaxIter(data.max_iterations)
  }, [data?.max_iterations])

  useEffect(() => { setMsg("") }, [editing])

  async function handlePickFolder() {
    try {
      const resp = await fetch("/api/settings/workspace/picker", { method: "POST" })
      const data = await resp.json()
      if (data.path) { setValue(data.path); await handleSave(data.path) }
    } catch { setMsg(t("general.select_fail")) }
  }

  async function handleSave(picked?: string) {
    const trimmed = (picked ?? value).trim()
    if (!trimmed) { setMsg(t("general.path_empty")); return }
    setSaving(true); setMsg("")
    try {
      const resp = await fetch("/api/settings/workspace", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: trimmed }),
      })
      resp.ok ? (setMsg("ok"), setEditing(false), onUpdate?.()) : setMsg("err")
    } catch { setMsg("err") } finally { setSaving(false) }
  }

  async function handleSaveTavily() {
    if (!tavilyKey.trim()) return
    setTavilySaving(true); setTavilyMsg("")
    try {
      const resp = await fetch("/api/settings/key", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "tavily", value: tavilyKey.trim() }),
      })
      resp.ok ? (setTavilyMsg("ok"), setTavilyEditing(false), onUpdate?.()) : setTavilyMsg("err")
    } catch { setTavilyMsg("err") } finally { setTavilySaving(false) }
  }

  async function handleSaveMaxIter() {
    setMaxIterSaving(true)
    try {
      const resp = await fetch("/api/settings/max-iterations", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: maxIter }),
      })
      resp.ok ? setMaxIterEditing(false) : null
    } catch {} finally { setMaxIterSaving(false) }
  }

  const msgLabel = msg === "ok" ? t("general.saved_ok") : msg === "err" ? t("general.save_fail") : msg

  return (
    <div className="space-y-5 stagger-1">
      <div className="rounded-xl border border-border/60 px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Folder className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">{t("general.workspace_title")}</h3>
        </div>
        <p className="text-xs text-muted-foreground/60 mb-3">{t("general.workspace_desc")}</p>
        {editing ? (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input type="text" value={value} onChange={e => setValue(e.target.value)} autoFocus placeholder="/home/user/my-project"
                className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm font-mono text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <button onClick={() => handleSave()} disabled={saving} className="h-9 px-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium flex items-center gap-1.5">
                <Check className="size-3.5" />{saving ? "..." : t("general.save_btn")}</button>
              <button onClick={() => { setEditing(false); if (data?.workspace) setValue(data.workspace) }} className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground">
                <X className="size-3.5" /></button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-9 px-3 rounded-lg border border-border bg-muted/30 flex items-center">
              <span className="text-sm font-mono text-foreground/80 truncate">{value || <span className="text-muted-foreground/40">{t("general.not_set")}</span>}</span>
            </div>
            <button onClick={handlePickFolder} className="h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground flex items-center gap-1.5">
              <FolderOpen className="size-3.5" />{t("general.choose")}</button>
            <button onClick={() => setEditing(true)} className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground">
              <Pencil className="size-3.5" /></button>
          </div>
        )}
        {msg && <p className={`text-xs mt-2 ${msg === "ok" ? "text-emerald-500" : "text-red-500"}`}>{msgLabel}</p>}
      </div>

      <div className="rounded-xl border border-border/60 px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Key className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">{t("general.tavily_title")}</h3>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${tavilyHasKey ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>
            {tavilyHasKey ? t("general.configured") : t("general.unconfigured")}</span>
        </div>
        {tavilyEditing ? (
          <div className="flex gap-2">
            <input type="password" value={tavilyKey} onChange={e => setTavilyKey(e.target.value)} autoFocus placeholder="tvly-..."
              className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/20" />
            <button onClick={handleSaveTavily} disabled={tavilySaving} className="h-9 px-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium flex items-center gap-1.5">
              <Check className="size-3.5" />{tavilySaving ? "..." : t("general.save_btn")}</button>
            <button onClick={() => setTavilyEditing(false)} className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground">
              <X className="size-3.5" /></button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-9 px-3 rounded-lg border border-border bg-muted/30 flex items-center">
              <span className="text-sm font-mono text-foreground/80">{tavilyHasKey ? "••••••••" : t("general.not_set")}</span>
            </div>
            <button onClick={() => { setTavilyEditing(true); setTavilyKey("") }} className="h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground flex items-center gap-1.5">
              <Pencil className="size-3.5" />{t("general.setup")}</button>
          </div>
        )}
        {tavilyMsg && <p className={`text-xs mt-2 ${tavilyMsg === "ok" ? "text-emerald-500" : "text-red-500"}`}>{tavilyMsg === "ok" ? t("general.saved_ok") : t("general.save_fail")}</p>}
      </div>

      <div className="rounded-xl border border-border/60 px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Repeat className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">{t("general.react_title")}</h3>
        </div>
        <p className="text-xs text-muted-foreground/60 mb-3">{t("general.react_desc")}</p>
        {maxIterEditing ? (
          <div className="flex gap-2">
            <input type="number" value={maxIter} onChange={e => setMaxIter(parseInt(e.target.value) || 30)} min={1} max={100}
              className="w-24 h-9 px-3 rounded-lg border border-border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/20" />
            <button onClick={handleSaveMaxIter} disabled={maxIterSaving} className="h-9 px-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium flex items-center gap-1.5">
              <Check className="size-3.5" />{maxIterSaving ? "..." : t("general.save_btn")}</button>
            <button onClick={() => { setMaxIterEditing(false); if (data?.max_iterations) setMaxIter(data.max_iterations) }} className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground">
              <X className="size-3.5" /></button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="h-9 px-3 rounded-lg border border-border bg-muted/30 flex items-center">
              <span className="text-sm font-mono text-foreground/80">{maxIter}</span>
            </div>
            <button onClick={() => setMaxIterEditing(true)} className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground">
              <Pencil className="size-3.5" /></button>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border/60 px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">{t("general.version_title")}</h3>
        <p className="text-xs text-muted-foreground/60 mt-0.5">CocoCat v2.0.0</p>
      </div>
    </div>
  )
}
