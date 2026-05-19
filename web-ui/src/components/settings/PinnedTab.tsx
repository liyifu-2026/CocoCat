import { useState, useEffect } from "react"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

export function PinnedTab() {
  const [facts, setFacts] = useState<string>("")
  const [newFact, setNewFact] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch("/api/pinned")
      .then(r => r.json())
      .then(d => setFacts(d.facts || ""))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const add = async () => {
    if (!newFact.trim()) return
    setSaving(true)
    try {
      const resp = await fetch("/api/pinned", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fact: newFact.trim() }),
      })
      if (!resp.ok) { toast.error("钉选失败"); return }
      setNewFact("")
      load()
    } finally { setSaving(false) }
  }

  const remove = async (fact: string) => {
    try {
      await fetch("/api/pinned", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: fact.slice(0, 20) }),
      })
      load()
    } catch { toast.error("删除失败") }
  }

  const lines = facts ? facts.split("\n").filter(l => l.trim()) : []

  if (loading) return <div className="flex items-center gap-2 text-sm text-muted-foreground py-3"><Loader2 className="size-4 animate-spin" /> 加载中...</div>

  return (
    <div className="space-y-4 py-3">
      <div className="flex gap-2">
        <input type="text" value={newFact} placeholder="添加钉选事实..." autoComplete="off"
          onChange={e => setNewFact(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") add() }}
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
        <button onClick={add} disabled={saving || !newFact.trim()}
          className="shrink-0 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 disabled:opacity-40 flex items-center gap-1.5">
          {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
          钉选
        </button>
      </div>

      {lines.length === 0 ? (
        <p className="text-xs text-muted-foreground">暂无钉选事实。Agent 对话中调用 pin 工具会自动添加。</p>
      ) : (
        <div className="space-y-1">
          {lines.map((line, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-border bg-background px-3 py-2">
              <span className="text-xs text-muted-foreground shrink-0 pt-0.5">#{i + 1}</span>
              <span className="text-xs flex-1">{line}</span>
              <button onClick={() => remove(line)}
                className="text-muted-foreground hover:text-destructive transition-colors p-0.5 shrink-0">
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
