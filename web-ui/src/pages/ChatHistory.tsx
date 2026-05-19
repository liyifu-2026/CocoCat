import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Search, MessageSquare } from "lucide-react"

interface HistoryItem {
  content: string
  role: string
  created_at: string
}

export default function ChatHistoryPage() {
  const [sessions, setSessions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [messages, setMessages] = useState<HistoryItem[]>([])
  const [search, setSearch] = useState("")
  const navigate = useNavigate()

  useEffect(() => {
    fetch("/api/chat/history?limit=200")
      .then(r => r.json())
      .then(d => setSessions(d.messages || []))
      .finally(() => setLoading(false))
  }, [])

  const openSession = async (content: string) => {
    if (expanded === content) { setExpanded(null); return }
    setExpanded(content)
    setMessages([])
    try {
      const resp = await fetch(`/api/chat/history?limit=50&q=${encodeURIComponent(content.slice(0, 30))}`)
      if (resp.ok) {
        const d = await resp.json()
        setMessages(d.messages || [])
      }
    } catch {}
  }

  const filtered = sessions.filter(s => {
    if (!search) return true
    const c = (s.content || "").toLowerCase()
    return c.includes(search.toLowerCase())
  })

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-4 h-13 flex items-center gap-3 shrink-0">
        <h1 className="text-sm font-display">对话历史</h1>
        <button onClick={() => navigate(-1)} className="text-xs text-muted-foreground hover:text-foreground ml-auto">返回</button>
      </div>

      <div className="px-4 py-3 border-b border-border/50">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input type="text" placeholder="搜索对话..." value={search}
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
            {filtered.map((s, i) => (
              <div key={i}>
                <button onClick={() => openSession(s.content)}
                  className="w-full text-left px-4 py-2.5 hover:bg-accent/50 transition-colors">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="size-3.5 text-muted-foreground shrink-0" />
                    <span className="text-xs truncate flex-1">{(s.content || "").slice(0, 80)}</span>
                    <span className="text-[10px] text-muted-foreground shrink-0">{s.created_at?.slice(0, 10)}</span>
                  </div>
                </button>
                {expanded === s.content && (
                  <div className="px-6 py-2 bg-muted/20 space-y-1 max-h-60 overflow-auto">
                    {messages.length === 0 ? <p className="text-[10px] text-muted-foreground"><Loader2 className="size-3 animate-spin inline mr-1" />加载中...</p> :
                      messages.map((m, j) => (
                        <div key={j} className="text-[10px]">
                          <span className="text-muted-foreground">{m.role === "user" ? "你" : "Coco"}: </span>
                          <span>{(m.content || "").slice(0, 200)}</span>
                        </div>
                      ))
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
