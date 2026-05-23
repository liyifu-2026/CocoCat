import { useSessionStore } from "@/hooks/useSessionStore"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { MessageSquare, Clock } from "lucide-react"
import type { QuickSendFn } from "../Layout"

interface Props {
  onQuickSend?: QuickSendFn
}

export default function DefaultFunc({ onQuickSend }: Props) {
  const store = useSessionStore("")
  const t = useT()

  const handleQuickAction = (action: string) => {
    if (onQuickSend) {
      onQuickSend(action)
    }
  }

  return (
    <div className="flex flex-col gap-3 p-4 animate-view-enter">
      {/* Quick Actions */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{t("quick.actions")}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {([
            { key: t("quick.analyze_project"), prompt: "Please analyze the current project and provide a summary." },
            { key: t("quick.create_task"), prompt: "Create a new task for me." },
            { key: t("quick.daily_summary"), prompt: "Give me a daily summary." },
            { key: t("quick.clear_memory"), prompt: "Clear your memory and start fresh." },
          ]).map((action) => (
            <button
              key={action.key}
              onClick={() => handleQuickAction(action.prompt)}
              className="bg-card border border-border rounded-xl p-3 text-left hover:border-primary/20 hover:shadow-sm transition-all group"
            >
              <div className="text-[10px] font-medium text-foreground group-hover:text-primary transition-colors">{action.key}</div>
              <div className="text-[8px] text-muted-foreground mt-0.5 line-clamp-1">{action.prompt.slice(0, 40)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Sessions */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{t("session.title")}</span>
          <button
            className="text-[9px] px-2 py-0.5 rounded-full border border-dashed border-border text-muted-foreground hover:border-primary/30 hover:text-primary transition-colors"
            onClick={() => store.newSession()}
          >
            + {t("session.new")}
          </button>
        </div>

        {[...store.sessions].sort((a, b) => b.createdAt - a.createdAt).slice(0, 6).length > 0 ? (
          <div className="space-y-1">
            {[...store.sessions].sort((a, b) => b.createdAt - a.createdAt).slice(0, 6).map(s => (
              <div
                key={s.id}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-lg text-[10px] cursor-pointer transition-all group",
                  s.id === store.currentId
                    ? "bg-primary/8 text-foreground border border-primary/10"
                    : "text-muted-foreground hover:bg-card hover:text-foreground"
                )}
                onClick={() => store.selectSession(s.id)}
              >
                <MessageSquare className={cn("size-3.5 shrink-0", s.id === store.currentId ? "text-primary" : "text-muted-foreground/40")} />
                <span className="truncate flex-1">{s.title || t("session.untitled")}</span>
                <span className="text-[9px] text-muted-foreground/40 flex items-center gap-1 shrink-0">
                  <Clock className="size-2.5" />
                  {timeAgo(s.createdAt)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-card border border-dashed border-border rounded-xl p-4 text-center">
            <MessageSquare className="size-4 text-muted-foreground/30 mx-auto mb-1" />
            <p className="text-[9px] text-muted-foreground/40">No sessions yet. Start a chat to create one.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.floor(hrs / 24)}d`
}
