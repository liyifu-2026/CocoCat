import { useState, useMemo } from "react"
import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Loader2, ChevronRight, ChevronDown, FileText, Link2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { transformWikilinks } from "@/lib/wikilink-transform"
import { cn } from "@/lib/utils"
import KbChatPanel from "@/components/KbChatPanel"

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

  const { data: graphData } = useQuery({
    queryKey: ["knowledge-graph", kb],
    queryFn: () => fetch(`/api/knowledge/${kb}/graph`).then(r => r.json()),
    enabled: !!kb,
  })

  const wiki = indexData as { entities?: string[]; concepts?: string[] } | null

  const pageLookup = useMemo(() => {
    const map: Record<string, string> = {}
    if (wiki?.entities) wiki.entities.forEach(n => { map[n] = "entities" })
    if (wiki?.concepts) wiki.concepts.forEach(n => { map[n] = "concepts" })
    return map
  }, [wiki])

  const knownPages = useMemo(() => new Set(Object.keys(pageLookup)), [pageLookup])

  const backlinks = useMemo(() => {
    if (!graphData || !selectedPage) return []
    const graph = (graphData as any)?.graph
    if (!graph?.links) return []
    const current = selectedPage.name
    const sources = new Set<string>()
    graph.links.forEach((link: any) => {
      if (link.target === current && link.source !== current) {
        sources.add(link.source)
      }
    })
    return Array.from(sources).map(name => ({
      name,
      type: pageLookup[name] || "entities",
    }))
  }, [graphData, selectedPage, pageLookup])

  const processedContent = useMemo(() => {
    const raw = (pageData as any)?.content ?? ""
    return transformWikilinks(raw)
  }, [pageData])

  const markdownComponents = useMemo(() => ({
    a({ href, children, ...props }: any) {
      if (href?.startsWith('#')) {
        const targetName = decodeURIComponent(href.slice(1))
        const targetType = pageLookup[targetName]
        const exists = knownPages.has(targetName)
        return (
          <button
            onClick={(e) => {
              e.preventDefault()
              if (targetType) {
                setSelectedPage({ type: targetType, name: targetName })
              }
            }}
            className={exists
              ? "text-primary underline underline-offset-2 hover:opacity-80 transition-opacity"
              : "text-muted-foreground/50 decoration-dashed underline underline-offset-2 cursor-not-allowed"
            }
            {...props}
          >
            {children}
          </button>
        )
      }
      return <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2" {...props}>{children}</a>
    }
  }), [pageLookup, knownPages])

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="flex h-full">
      <nav className="w-56 border-r border-border overflow-y-auto p-3 space-y-3 shrink-0">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{kb}</h3>
        {wiki && (
          <>
            <Section title="Entities" items={wiki.entities ?? []} selected={selectedPage} onSelect={(n) => setSelectedPage({ type: "entities", name: n })} />
            <Section title="Concepts" items={wiki.concepts ?? []} selected={selectedPage} onSelect={(n) => setSelectedPage({ type: "concepts", name: n })} />
          </>
        )}
      </nav>
      <main className="flex-1 overflow-auto p-6">
        {pageData ? (
          <div className="max-w-3xl">
            <h1 className="text-xl font-bold mb-4">{(pageData as any)?.name ?? selectedPage?.name}</h1>
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {processedContent}
              </ReactMarkdown>
            </div>
            {backlinks.length > 0 && (
              <div className="mt-8 pt-6 border-t border-border">
                <h2 className="text-sm font-medium text-muted-foreground flex items-center gap-1.5 mb-3">
                  <Link2 className="size-3.5" />
                  Backlinks ({backlinks.length})
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {backlinks.map(bl => (
                    <button
                      key={bl.name}
                      onClick={() => setSelectedPage(bl)}
                      className="text-xs px-2.5 py-1 rounded-md bg-muted hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {bl.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="size-8 mb-2 opacity-40" />
            <p className="text-sm">选择一个页面查看</p>
          </div>
        )}
      </main>
      <div className="w-72 shrink-0">
        <KbChatPanel kbName={kb!} />
      </div>
    </div>
  )
}

function Section({ title, items, selected, onSelect }: { title: string; items: string[]; selected: { type: string; name: string } | null; onSelect: (name: string) => void }) {
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
            <button
              key={item}
              onClick={() => onSelect(item)}
              className={cn(
                "block w-full text-left text-xs px-3 py-1.5 rounded transition-colors",
                selected?.name === item && selected?.type?.toLowerCase() === title.toLowerCase()
                  ? "bg-accent text-foreground"
                  : "hover:bg-accent text-muted-foreground hover:text-foreground"
              )}
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
