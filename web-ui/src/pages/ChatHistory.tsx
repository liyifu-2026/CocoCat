import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Search, MessageSquare } from "lucide-react"

export default function ChatHistoryPage() {
  const [sessions, setSessions] = useState<{ id: string; title: string; count: number; date: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const navigate = useNavigate()

  useEffect(() => {
    fetch("/api/chat/history?limit=500")
      .then(r => r.json())
      .then(d => {
        const msgs = d.messages || []
        const seen = new Map<string, { title: string; count: number; date: string }>()
        for (const m of msgs) {
          const sid = m.session_id || "default"
          if (!seen.has(sid)) {
            seen.set(sid, { title: (m.content || "").slice(0, 60), count: 0, date: m.created_at?.slice(0, 10) || "" })
          }
          const entry = seen.get(sid)!
          entry.count++
        }
        setSessions(Array.from(seen.entries()).map(([id, v]) => ({ id, ...v })))
      })
      .finally(() => setLoading(false))
  }, [])

  const filtered = sessions.filter(s =>
    !search || s.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-4 h-13 flex items-center gap-3 shrink-0">
        <h1 className="text-sm font-display">对话历史</h1>
        <button onClick={() => navigate(-1)} className="text-xs text-muted-foreground hover:text-foreground ml-auto">返回</button>
      </div>
      <div className="px-4 py-3 border-b border-border/50">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input type="text" placeholder="搜索..." value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground"><Loader2 className="size-4 animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">暂无对话</div>
        ) : (
          <div className="divide-y divide-border/30">
            {filtered.map(s => (
              <div key={s.id} className="hover:bg-accent/50 transition-colors px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <MessageSquare className="size-3.5 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs truncate">{s.title || "(空消息)"}</div>
                    <div className="text-[10px] text-muted-foreground">{s.count} 条消息 · {s.date}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
