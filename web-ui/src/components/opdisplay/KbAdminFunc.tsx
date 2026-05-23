import Bookshelf from "./Bookshelf"
import { useT } from "@/context/LanguageContext"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import type { QuickSendFn } from "../Layout"

interface Props {
  onQuickSend?: QuickSendFn
}

export default function KbAdminFunc({ onQuickSend }: Props) {
  const t = useT()

  const { data } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })
  const kbs = (data as any)?.kbs ?? []

  const handleQuickAction = (prompt: string) => {
    if (onQuickSend) onQuickSend(prompt)
  }

  return (
    <div className="flex flex-col animate-view-enter">
      <Bookshelf />

      <div className="px-4 pb-4 space-y-3">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{t("quick.actions")}</span>
            {kbs.length > 0 && <span className="text-[9px] text-muted-foreground/50">{kbs.length} KB active</span>}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {([
              { label: t("quick.analyze_project"), icon: "📊", prompt: "Please analyze the current project structure and all knowledge bases." },
              { label: t("quick.create_task"), icon: "📝", prompt: "Create a new task for me based on the current knowledge bases." },
              { label: t("quick.daily_summary"), icon: "📋", prompt: "Give me a daily summary of all knowledge base activities." },
              { label: t("quick.clear_memory"), icon: "🧹", prompt: "Clear your memory and start fresh with the knowledge bases." },
            ]).map(a => (
              <button
                key={a.label}
                onClick={() => handleQuickAction(a.prompt)}
                className="bg-card border border-border rounded-xl p-3 text-left hover:border-accent/20 hover:shadow-sm transition-all group"
              >
                <div className="text-sm mb-1">{a.icon}</div>
                <div className="text-[9px] font-medium text-muted-foreground group-hover:text-foreground transition-colors">{a.label}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
