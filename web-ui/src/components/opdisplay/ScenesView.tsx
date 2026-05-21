import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Play, Pause, Archive, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"
import { Skeleton } from "@/components/ui/skeleton"

interface Scene {
  id: string
  name: string
  description: string
  status: string
  purpose: string
  kbs: string[]
  skills: string[]
  channels: string[]
  created_at: string
}

const STATUS_STYLES: Record<string, string> = {
  running: "bg-emerald-500/10 text-emerald-400",
  paused: "bg-amber-500/10 text-amber-400",
  archived: "bg-blue-500/10 text-blue-400",
}

export default function ScenesView() {
  const queryClient = useQueryClient()
  const t = useT()
  const { data: scenes, isLoading } = useQuery<Scene[]>({
    queryKey: ["scenes"],
    queryFn: async () => {
      const res = await fetch("/api/scenes")
      if (!res.ok) throw new Error("Failed to fetch scenes")
      return res.json()
    },
  })

  const doAction = async (id: string, action: string) => {
    await fetch(`/api/scenes/${id}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
    queryClient.invalidateQueries({ queryKey: ["scenes"] })
  }

  return (
    <div className="flex flex-col h-full animate-view-enter">
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
        <h2 className="text-sm font-semibold">Scenes</h2>
        <div className="flex-1" />
        {scenes && <span className="text-[9px] text-muted-foreground bg-card border border-border rounded-full px-2.5 py-1">{scenes.length} total</span>}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="space-y-2.5">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-[100px] w-full rounded-xl shimmer-skeleton" />
            ))}
          </div>
        )}

        {!isLoading && scenes && scenes.length === 0 && (
          <p className="text-[11px] text-muted-foreground text-center py-8">{t("scene.no_scenes_short")}</p>
        )}

        {!isLoading && scenes && (
          <div className="grid gap-2.5">
            {scenes.map(scene => (
              <div key={scene.id} className="bg-card border border-border rounded-xl p-4 space-y-3 stagger-1">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-medium">{scene.name}</h3>
                      <span className={cn("text-[9px] px-2 py-0.5 rounded-full font-medium", STATUS_STYLES[scene.status] || "bg-muted text-muted-foreground")}>
                        {t(`scene.${scene.status}`) || scene.status}
                      </span>
                    </div>
                    {scene.purpose && <p className="text-[10px] text-muted-foreground line-clamp-2">{scene.purpose}</p>}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {scene.status === "paused" && (
                      <button onClick={() => doAction(scene.id, "resume")} className="p-1.5 rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-400 transition-colors"><Play className="size-3.5" /></button>
                    )}
                    {scene.status === "running" && (
                      <button onClick={() => doAction(scene.id, "pause")} className="p-1.5 rounded-lg hover:bg-amber-500/10 text-muted-foreground hover:text-amber-400 transition-colors"><Pause className="size-3.5" /></button>
                    )}
                    {scene.status !== "archived" && (
                      <button onClick={() => doAction(scene.id, "archive")} className="p-1.5 rounded-lg hover:bg-blue-500/10 text-muted-foreground hover:text-blue-400 transition-colors"><Archive className="size-3.5" /></button>
                    )}
                    <button onClick={() => doAction(scene.id, "delete")} className="p-1.5 rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-colors"><Trash2 className="size-3.5" /></button>
                  </div>
                </div>
                {(scene.kbs?.length > 0 || scene.skills?.length > 0 || scene.channels?.length > 0) && (
                  <div className="flex flex-wrap gap-1">
                    {scene.kbs?.map(kb => <span key={kb} className="text-[8px] bg-muted border border-border rounded-full px-2 py-0.5 text-muted-foreground">{kb}</span>)}
                    {scene.skills?.map(s => <span key={s} className="text-[8px] bg-accent/10 border border-accent/20 rounded-full px-2 py-0.5 text-accent">{s}</span>)}
                    {scene.channels?.map(c => <span key={c} className="text-[8px] bg-primary/10 border border-primary/20 rounded-full px-2 py-0.5 text-primary">{c}</span>)}
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
