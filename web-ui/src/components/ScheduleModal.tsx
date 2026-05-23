import { useState, useEffect, useCallback, useRef } from "react"
import { X, Clock, Bell, Pause, Play, Trash2, Plus, Loader2, ChevronDown } from "lucide-react"
import { useT } from "@/context/LanguageContext"

interface CronEntry {
  id: string
  agent_id: string
  name: string
  schedule: string
  task: string
  status: string
  last_run: number | string | null
  at_time?: string | null
  created_at: string
  error?: string | null
  next_run?: string | null
}

interface ScheduleModalProps {
  open: boolean
  onClose: () => void
}

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"))
const MINUTES = ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"]

function TimePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const hourRef = useRef<HTMLDivElement>(null)
  const minRef = useRef<HTMLDivElement>(null)
  const [h, m] = (value || "09:00").split(":")

  useEffect(() => {
    const hIdx = HOURS.indexOf(h || "09")
    const mIdx = MINUTES.indexOf(m || "00")
    if (hourRef.current) hourRef.current.scrollTop = Math.max(0, hIdx - 1) * 36
    if (minRef.current) minRef.current.scrollTop = Math.max(0, mIdx - 1) * 36
  }, [value])

  const snap = () => {
    if (!hourRef.current || !minRef.current) return
    const hIdx = Math.round(hourRef.current.scrollTop / 36)
    const mIdx = Math.round(minRef.current.scrollTop / 36)
    const newH = HOURS[Math.min(Math.max(hIdx, 0), 23)]
    const newM = MINUTES[Math.min(Math.max(mIdx, 0), 11)]
    onChange(`${newH}:${newM}`)
  }

  return (
    <div className="relative border border-border rounded-xl overflow-hidden bg-card" style={{ height: 128 }}>
      <div className="absolute top-1/2 left-2 right-2 -translate-y-1/2 h-9 border-t border-primary/30 border-b border-primary/30 rounded bg-primary/[0.03] pointer-events-none z-0" />
      <div className="flex justify-center gap-2 h-full relative z-10">
        <div
          ref={hourRef}
          className="w-16 overflow-y-scroll scroll-snap-y snap-y snap-mandatory no-scrollbar cursor-grab text-center py-10"
          onScroll={() => snap()}
          onMouseUp={snap}
          onTouchEnd={snap}
        >
          {HOURS.map(item => (
            <div
              key={item}
              className={`snap-center h-9 flex items-center justify-center text-lg font-semibold transition-colors ${item === h ? "text-primary" : "text-muted-foreground/50"}`}
            >
              {item}
            </div>
          ))}
        </div>
        <span className="text-lg font-light text-muted-foreground self-center">:</span>
        <div
          ref={minRef}
          className="w-16 overflow-y-scroll snap-y snap-mandatory no-scrollbar cursor-grab text-center py-10"
          onScroll={() => snap()}
          onMouseUp={snap}
          onTouchEnd={snap}
        >
          {MINUTES.map(item => (
            <div
              key={item}
              className={`snap-center h-9 flex items-center justify-center text-lg font-semibold transition-colors ${item === m ? "text-primary" : "text-muted-foreground/50"}`}
            >
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function ScheduleModal({ open, onClose }: ScheduleModalProps) {
  const t = useT()
  const FREQ_OPTIONS = [
    { value: "hourly", labelKey: "schedule.freq_hourly" },
    { value: "daily", labelKey: "schedule.freq_daily" },
    { value: "weekly", labelKey: "schedule.freq_weekly" },
    { value: "every 6 hours", labelKey: "schedule.freq_6h" },
    { value: "every 12 hours", labelKey: "schedule.freq_12h" },
    { value: "every 15 minutes", labelKey: "schedule.freq_15m" },
    { value: "every 30 minutes", labelKey: "schedule.freq_30m" },
  ]

  const SCHEDULE_LABELS: Record<string, string> = Object.fromEntries(
    FREQ_OPTIONS.map(o => [o.value, t(o.labelKey)])
  )

  function scheduleLabel(schedule: string): string {
    const s = schedule.replace(/^@/, "").toLowerCase()
    return SCHEDULE_LABELS[s] || schedule
  }

  const [entries, setEntries] = useState<CronEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [usePreciseTime, setUsePreciseTime] = useState(false)

  const [form, setForm] = useState({
    id: "",
    name: "",
    agent_id: "",
    schedule: "daily",
    task: "",
    at_time: "",
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const cronRes = await fetch("/api/cron")
      const cronData = await cronRes.json()
      setEntries(cronData.entries || [])
    } catch {
      setError("Failed to load data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) fetchData()
  }, [open, fetchData])

  function resetForm() {
    setForm({ id: "", name: "", agent_id: "", schedule: "daily", task: "", at_time: "" })
    setEditingId(null)
    setUsePreciseTime(false)
  }

  function startEdit(entry: CronEntry) {
    setForm({
      id: entry.id,
      name: entry.name,
      agent_id: entry.agent_id,
      schedule: entry.schedule,
      task: entry.task,
      at_time: entry.at_time || "",
    })
    setEditingId(entry.id)
    setUsePreciseTime(!!entry.at_time)
    setShowForm(true)
  }

  async function handleSave() {
    if (!form.id.trim() || !form.task.trim() || !form.schedule.trim()) return
    setSaving(true)
    setError("")
    const body: any = { schedule: form.schedule, task: form.task, at_time: usePreciseTime ? form.at_time : null }
    try {
      if (editingId) {
        const res = await fetch(`/api/cron/${encodeURIComponent(editingId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
        if (!res.ok) {
          const d = await res.json()
          throw new Error(d.detail || "Update failed")
        }
        setEntries(prev =>
          prev.map(e => (e.id === editingId ? { ...e, schedule: form.schedule, task: form.task, at_time: body.at_time, name: form.name } : e))
        )
      } else {
        Object.assign(body, { id: form.id, agent_id: form.agent_id, name: form.name })
        const res = await fetch("/api/cron", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
        if (!res.ok) {
          const d = await res.json()
          throw new Error(d.detail || "Create failed")
        }
        const created = await res.json()
        setEntries(prev => [...prev, created])
      }
      resetForm()
      setShowForm(false)
    } catch (e: any) {
      setError(e.message || "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function togglePause(entry: CronEntry) {
    const newStatus = entry.status === "active" ? "paused" : "active"
    try {
      const res = await fetch(`/api/cron/${encodeURIComponent(entry.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      })
      if (!res.ok) throw new Error("Failed")
      setEntries(prev =>
        prev.map(e => (e.id === entry.id ? { ...e, status: newStatus } : e))
      )
    } catch {
      setError("Failed to update status")
    }
  }

  async function deleteEntry(id: string) {
    try {
      const res = await fetch(`/api/cron/${encodeURIComponent(id)}`, { method: "DELETE" })
      if (!res.ok) throw new Error("Failed")
      setEntries(prev => prev.filter(e => e.id !== id))
    } catch {
      setError("Failed to delete")
    }
  }

  function formatNextRun(nextRun: string | null | undefined): string {
    if (!nextRun) return "—"
    try {
      const next = new Date(nextRun)
      const now = new Date()
      const diffMs = next.getTime() - now.getTime()
      if (diffMs <= 0) return t("schedule.anytime")
      const diffMin = Math.ceil(diffMs / 60000)
      if (diffMin < 60) return `${diffMin}${t("schedule.min_after")}`
      const diffHr = Math.ceil(diffMin / 60)
      if (diffHr < 24) return `${diffHr}${t("schedule.hr_after")}`
      return next.toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    } catch {
      return "—"
    }
  }

  function formatLastRun(lastRun: number | string | null): string {
    if (lastRun == null || lastRun === 0) return t("schedule.not_run")
    let ts: number
    if (typeof lastRun === "string") {
      ts = Date.parse(lastRun)
    } else {
      ts = typeof lastRun === "number" && lastRun < 10000000000 ? lastRun * 1000 : lastRun
    }
    if (isNaN(ts)) return t("schedule.not_run")
    const ago = Math.round((Date.now() - ts) / 60000)
    if (ago < 1) return t("schedule.just_now")
    if (ago < 60) return `${ago}${t("schedule.min_ago")}`
    if (ago < 1440) return `${Math.round(ago / 60)}${t("schedule.hr_ago")}`
    return `${Math.round(ago / 1440)}${t("schedule.day_ago")}`
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-[560px] max-h-[85vh] rounded-2xl bg-card shadow-2xl border border-border/50 flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
        style={{ animation: "fadeSlideUp 0.2s ease-out both" }}
      >
        <div className="flex items-center justify-between border-b border-border px-5 h-13 shrink-0">
          <h2 className="text-sm font-display text-foreground flex items-center gap-2">
            <Clock className="size-4 text-tertiary" />
              {t("schedule.title_modal")}
          </h2>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-600">{error}</div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
              <Loader2 className="size-4 animate-spin" />
              {t("schedule.loading")}
          </div>
          ) : (
            <>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Bell className="size-4 text-primary/70" />
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{t("schedule.title_modal")}</h3>
                    {entries.length > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">{entries.length}</span>
                    )}
                  </div>
                  <button
                    onClick={() => { resetForm(); setShowForm(!showForm) }}
                    className="text-xs text-primary hover:text-primary/80 font-medium transition-colors flex items-center gap-1"
                  >
                    <Plus className="size-3" />
                    {t("schedule.new")}
                  </button>
                </div>

                {showForm && (
                  <div className="rounded-xl border border-primary/30 bg-card px-4 py-3.5 space-y-3 mb-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wider">{t("schedule.id_label")}</label>
                        <input
                          className="w-full rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary transition-colors"
                          value={form.id}
                          onChange={e => setForm({ ...form, id: e.target.value })}
                          placeholder="my-task"
                          disabled={!!editingId}
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wider">{t("schedule.name_label")}</label>
                        <input
                          className="w-full rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary transition-colors"
                          value={form.name}
                          onChange={e => setForm({ ...form, name: e.target.value })}
                          placeholder="任务名称"
                        />
                      </div>
                    </div>
                    <div>
                        <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wider">{t("schedule.freq_label")}</label>
                      <select
                        className="w-full rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary transition-colors"
                        value={form.schedule}
                        onChange={e => setForm({ ...form, schedule: e.target.value })}
                      >
                        {FREQ_OPTIONS.map(o => (
                          <option key={o.value} value={o.value}>{t(o.labelKey)}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="flex items-center gap-2 text-[10px] text-muted-foreground mb-1 uppercase tracking-wider cursor-pointer select-none"
                        onClick={() => setUsePreciseTime(!usePreciseTime)}
                      >
                        <span className={`w-3.5 h-3.5 rounded border-2 flex items-center justify-center transition-all ${usePreciseTime ? "bg-primary border-primary" : "border-muted-foreground/30"}`}>
                          {usePreciseTime && <span className="block w-1.5 h-1.5 bg-primary-foreground rounded-[1px]" />}
                        </span>
                        {t("schedule.alarm_mode")}
                      </label>
                      {usePreciseTime && (
                        <div className="mt-2">
                          <TimePicker
                            value={form.at_time || "09:00"}
                            onChange={v => setForm({ ...form, at_time: v })}
                          />
                          <button
                            className="text-[10px] text-muted-foreground/60 hover:text-foreground mt-1.5 block mx-auto transition-colors"
                            onClick={() => { setUsePreciseTime(false); setForm({ ...form, at_time: "" }) }}
                          >
                            {t("schedule.clear_time")}
                          </button>
                        </div>
                      )}
                    </div>
                    {usePreciseTime && form.at_time && (
                      <div className="px-3 py-2 rounded-lg bg-primary/[0.06] border border-primary/20 text-xs text-primary flex items-center gap-1.5">
                        <span>🔔</span>
                        {scheduleLabel(form.schedule)} <strong>{form.at_time}</strong> {t("schedule.will_run")}
                      </div>
                    )}
                    <div>
                        <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wider">{t("schedule.task_label")}</label>
                      <textarea
                        className="w-full rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary transition-colors resize-none h-20"
                        value={form.task}
                        onChange={e => setForm({ ...form, task: e.target.value })}
                        placeholder={t("schedule.task_placeholder")}
                      />
                    </div>
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {saving && <Loader2 className="size-3 animate-spin" />}
                        {editingId ? t("schedule.save_edit") : t("schedule.create_task_btn")}
                      </button>
                      <button
                        onClick={() => { resetForm(); setShowForm(false) }}
                        className="px-4 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                      >
                        {t("schedule.cancel")}
                      </button>
                    </div>
                  </div>
                )}

                {entries.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground/60">{t("schedule.empty")}</div>
                ) : (
                  <div className="space-y-2">
                    {entries.map(e => {
                      const isAlarm = !!(e.at_time && e.at_time.length > 0)
                      return (
                        <div key={e.id} className={`rounded-xl border px-4 py-3 hover:shadow-sm transition-all duration-200 ${e.status === "paused" ? "border-amber-500/30 bg-amber-500/5" : "border-border/60"}`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${e.status === "active" ? "bg-emerald-400" : "bg-amber-400"}`} />
                              <span className="text-sm font-medium text-foreground truncate">
                                {isAlarm ? "🔔" : "🔄"} {scheduleLabel(e.schedule)}
                              </span>
                              {isAlarm && (
                                <span className="text-xs font-mono text-primary/80">{e.at_time}</span>
                              )}
                              <span className="text-xs text-muted-foreground/70 bg-muted/50 rounded-full px-2 py-0.5 truncate max-w-[180px]">{e.task}</span>
                            </div>
                            <div className="flex items-center gap-1 shrink-0 ml-2">
                              {e.status === "failed" && e.error && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-500 max-w-[120px] truncate" title={e.error}>{e.error}</span>
                              )}
                              <button onClick={() => togglePause(e)} className="w-6 h-6 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all" title={e.status === "active" ? "Pause" : "Resume"}>
                                {e.status === "active" ? <Pause className="size-3" /> : <Play className="size-3" />}
                              </button>
                              <button onClick={() => startEdit(e)} className="text-xs text-muted-foreground/70 hover:text-primary hover:bg-accent rounded-lg px-1.5 py-0.5 transition-colors">{t("schedule.edit_btn")}</button>
                              <button onClick={() => { if (confirm(t("schedule.confirm_delete"))) deleteEntry(e.id) }} className="w-6 h-6 rounded-lg flex items-center justify-center text-muted-foreground/50 hover:text-red-400 hover:bg-red-400/10 transition-all">
                                <Trash2 className="size-3" />
                              </button>
                            </div>
                          </div>
                          <div className="flex items-center gap-4 mt-2">
                            <span className="text-xs text-muted-foreground/60">{t("schedule.last_run")}{formatLastRun(e.last_run)}</span>
                            <span className="text-xs text-muted-foreground/60">{t("schedule.next_run")}{formatNextRun(e.next_run)}</span>
                            {e.agent_id && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/50 text-muted-foreground/70">{e.agent_id}</span>
                            )}
                            {e.status === "paused" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600">{t("schedule.paused")}</span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
