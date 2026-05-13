import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { BookOpen, Loader2 } from "lucide-react"

export default function KnowledgePage() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const kbs = (data as { kbs?: { id: string; purpose?: string }[] })?.kbs ?? []

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3 mb-6">
        <BookOpen className="size-5 text-muted-foreground" />
        <h1 className="text-lg font-bold">知识库</h1>
      </div>
      {kbs.length === 0 && (
        <p className="text-sm text-muted-foreground">暂无知识库</p>
      )}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {kbs.map(kb => (
          <button
            key={kb.id}
            onClick={() => navigate(`/knowledge/${kb.id}`)}
            className="rounded-xl border border-border/60 bg-card p-5 text-left hover:shadow-sm transition-shadow duration-200 space-y-2"
          >
            <h3 className="font-medium">{kb.id}</h3>
            {kb.purpose && <p className="text-xs text-muted-foreground line-clamp-3">{kb.purpose}</p>}
          </button>
        ))}
      </div>
    </div>
  )
}
