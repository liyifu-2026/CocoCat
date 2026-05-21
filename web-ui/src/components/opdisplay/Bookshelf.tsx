import { useQuery } from "@tanstack/react-query"
import { cn } from "@/lib/utils"

const COVER_COLORS = [
  "bg-gradient-to-br from-blue-600 to-blue-800",
  "bg-gradient-to-br from-indigo-600 to-indigo-800",
  "bg-gradient-to-br from-cyan-600 to-cyan-800",
  "bg-gradient-to-br from-amber-600 to-amber-800",
  "bg-gradient-to-br from-rose-600 to-rose-800",
  "bg-gradient-to-br from-emerald-600 to-emerald-800",
  "bg-gradient-to-br from-violet-600 to-violet-800",
  "bg-gradient-to-br from-sky-600 to-sky-800",
]

export default function Bookshelf() {
  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const kbs = (data as any)?.kbs ?? []

  if (isLoading) {
    return (
      <div className="p-4 text-center">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-muted rounded w-1/3 mx-auto" />
          <div className="grid grid-cols-4 gap-3">
            {[1,2,3,4].map(i => <div key={i} className="aspect-[3/4] rounded-lg bg-card animate-pulse" />)}
          </div>
        </div>
      </div>
    )
  }

  if (kbs.length === 0) {
    return (
      <div className="p-8 text-center">
        <p className="text-[11px] text-muted-foreground/50">No knowledge bases yet. Switch to kb-admin mode and use Chat to create one.</p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-semibold text-amber-400">📁 Knowledge Bases</span>
          <span className="text-[9px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full">{kbs.length} books</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {kbs.map((kb: any, i: number) => (
            <div key={kb.id} className="group cursor-pointer transition-all duration-200 hover:-translate-y-1">
              <div className={cn("aspect-[3/4] rounded-lg flex items-center justify-center text-[9px] font-medium text-white text-center leading-tight p-2", COVER_COLORS[i % COVER_COLORS.length])}>
                {kb.id}
              </div>
              <p className="text-[8px] text-muted-foreground mt-1.5 text-center truncate">{kb.id}</p>
            </div>
          ))}
          <div className="aspect-[3/4] rounded-lg border border-dashed border-border flex items-center justify-center cursor-pointer hover:border-amber-500/30 transition-colors">
            <span className="text-muted-foreground/40 text-lg">+</span>
          </div>
        </div>
      </div>
      <div className="border border-dashed border-border rounded-lg py-2.5 text-center text-[9px] text-muted-foreground/50 cursor-pointer hover:border-amber-500/20 hover:text-amber-400 transition-colors">
        + Add New Category Shelf
      </div>
    </div>
  )
}
