import { useSessionStore } from "@/hooks/useSessionStore"
import { cn } from "@/lib/utils"

export default function DefaultFunc() {
  const store = useSessionStore("")

  return (
    <div className="flex flex-col gap-2.5 p-4">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2.5">📋 Sessions</div>
        <button
          className="w-full border border-dashed border-border rounded-lg text-center py-2 text-[10px] text-muted-foreground/60 hover:border-primary/30 hover:text-muted-foreground transition-colors mb-2"
          onClick={() => store.newSession()}
        >
          + New Session
        </button>
        {[...store.sessions].sort((a, b) => b.createdAt - a.createdAt).slice(0, 5).map(s => (
          <div
            key={s.id}
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 rounded-md text-[10px] cursor-pointer transition-colors",
              s.id === store.currentId ? "bg-primary/8 text-foreground" : "text-muted-foreground hover:bg-card/50"
            )}
            onClick={() => store.selectSession(s.id)}
          >
            <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", s.id === store.currentId ? "bg-primary" : "bg-muted-foreground/30")} />
            <span className="truncate flex-1">{s.title || "Untitled"}</span>
            <span className="text-[9px] text-muted-foreground/50 shrink-0">
              {timeAgo(s.createdAt)}
            </span>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2">🔧 Quick Actions</div>
        <div className="flex flex-wrap gap-1.5">
          {["分析当前项目", "创建新任务", "今日摘要", "清理记忆"].map(action => (
            <span key={action} className="inline-block bg-muted/50 border border-border rounded-full px-2.5 py-1 text-[9px] text-muted-foreground cursor-pointer hover:bg-muted hover:text-foreground transition-colors">
              {action}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
