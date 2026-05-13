import { useState } from "react"
import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Loader2, ChevronRight, ChevronDown, FileText } from "lucide-react"

export default function KnowledgeDetailPage() {
  const { kb } = useParams<{ kb: string }>()
  const [selectedPage, setSelectedPage] = useState<{ type: string; name: string } | null>(null)

  const { data: indexData, isLoading } = useQuery({
    queryKey: ["knowledge-index", kb],
    queryFn: () => fetch(`/api/knowledge/${kb}/wiki`).then(r => r.json()),
    enabled: !!kb,
  })

  const { data: pageData } = useQuery({
    queryKey: ["knowledge-page", kb, selectedPage?.type, selectedPage?.name],
    queryFn: () => fetch(`/api/knowledge/${kb}/wiki/${selectedPage!.type}/${selectedPage!.name}`).then(r => r.json()),
    enabled: !!selectedPage && !!kb,
  })

  const wiki = indexData as { entities?: string[]; concepts?: string[] } | null

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="flex h-full">
      <nav className="w-56 border-r border-border overflow-y-auto p-3 space-y-3 shrink-0">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{kb}</h3>
        {wiki && (
          <>
            <Section title="Entities" items={wiki.entities ?? []} onSelect={(n) => setSelectedPage({ type: "entities", name: n })} />
            <Section title="Concepts" items={wiki.concepts ?? []} onSelect={(n) => setSelectedPage({ type: "concepts", name: n })} />
          </>
        )}
      </nav>
      <main className="flex-1 overflow-auto p-6">
        {pageData ? (
          <div className="max-w-3xl">
            <h1 className="text-xl font-bold mb-4">{(pageData as any)?.name ?? selectedPage?.name}</h1>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{(pageData as any)?.content ?? ""}</pre>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="size-8 mb-2 opacity-40" />
            <p className="text-sm">选择一个页面查看</p>
          </div>
        )}
      </main>
    </div>
  )
}

function Section({ title, items, onSelect }: { title: string; items: string[]; onSelect: (name: string) => void }) {
  const [collapsed, setCollapsed] = useState(false)
  if (items.length === 0) return null
  return (
    <div>
      <button onClick={() => setCollapsed(!collapsed)} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground w-full text-left">
        {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
        {title} ({items.length})
      </button>
      {!collapsed && (
        <div className="mt-1 space-y-0.5">
          {items.map(item => (
            <button key={item} onClick={() => onSelect(item)} className="block w-full text-left text-xs px-3 py-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
