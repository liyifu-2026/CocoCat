import { useState, useMemo, useCallback } from "react"
import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Loader2, ChevronRight, ChevronDown, FileText, Link2, Search, X, BookOpen } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { transformWikilinks } from "@/lib/wikilink-transform"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import Chat from "@/pages/Chat"

export default function KnowledgeDetailPage() {
  const { kb } = useParams<{ kb: string }>()
  const [selectedPage, setSelectedPage] = useState<{ type: string; name: string } | null>(null)
  const [search, setSearch] = useState("")
  const t = useT()

  const { data: indexData, isLoading } = useQuery({
    queryKey: ["knowledge-index", kb],
    queryFn: () => fetch(`/api/knowledge/${kb}/wiki`).then(r => r.json()),
    enabled: !!kb,
  })

  const { data: pageData, isLoading: pageLoading } = useQuery({
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

  const searchFiltered = useMemo(() => {
    if (!search.trim()) return { entities: wiki?.entities ?? [], concepts: wiki?.concepts ?? [] }
    const q = search.toLowerCase()
    return {
      entities: (wiki?.entities ?? []).filter(n => n.toLowerCase().includes(q)),
      concepts: (wiki?.concepts ?? []).filter(n => n.toLowerCase().includes(q)),
    }
  }, [wiki, search])

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

  const handleSelect = useCallback((type: string, name: string) => {
    setSelectedPage({ type, name })
    setSearch("")
  }, [])

  if (isLoading) {
    return (
      <div className="flex h-full">
        <nav className="w-56 border-r border-border p-3 space-y-3 shrink-0">
          <Skeleton className="h-5 w-24 shimmer-skeleton" />
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-full rounded shimmer-skeleton" />
          ))}
        </nav>
        <main className="flex-1 flex items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-full animate-view-enter">
      {/* Left Nav */}
      <nav className="w-56 border-r border-border overflow-y-auto shrink-0 flex flex-col">
        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
            <BookOpen className="size-3.5 text-muted-foreground" />
            {kb}
          </h3>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={t("knowledge.search_wiki")}
              className="w-full rounded-lg border border-border bg-input pl-7 pr-7 py-1.5 text-[11px] outline-none focus:border-primary/30 transition-colors"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="size-3" />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {wiki ? (
            <>
              <Section
                title={t("knowledge.entities")}
                items={searchFiltered.entities}
                selected={selectedPage}
                onSelect={(n) => handleSelect("entities", n)}
              />
              <Section
                title={t("knowledge.concepts")}
                items={searchFiltered.concepts}
                selected={selectedPage}
                onSelect={(n) => handleSelect("concepts", n)}
              />
            </>
          ) : (
            <p className="text-[11px] text-muted-foreground text-center py-8">{t("knowledge.no_kb_desc")}</p>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {pageLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton className="h-7 w-48 shimmer-skeleton" />
            <Skeleton className="h-4 w-32 shimmer-skeleton" />
            <div className="space-y-2 mt-6">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className={cn("h-4 rounded shimmer-skeleton", i % 3 === 0 ? "w-full" : i % 3 === 1 ? "w-3/4" : "w-1/2")} />
              ))}
            </div>
          </div>
        ) : pageData ? (
          <div className="max-w-3xl mx-auto p-6">
            {/* Breadcrumb */}
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-4">
              <BookOpen className="size-3" />
              <span className="font-medium">{kb}</span>
              <ChevronRight className="size-3" />
              <span className="text-foreground">{(pageData as any)?.name ?? selectedPage?.name}</span>
            </div>

            <h1 className="text-xl font-bold text-foreground mb-1">{(pageData as any)?.name ?? selectedPage?.name}</h1>
            <p className="text-[10px] text-muted-foreground mb-6">
              {selectedPage?.type === "entities" ? t("knowledge.entities") : t("knowledge.concepts")}
            </p>

            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {processedContent}
              </ReactMarkdown>
            </div>

            {backlinks.length > 0 && (
              <div className="mt-8 pt-6 border-t border-border">
                <h2 className="text-sm font-medium text-muted-foreground flex items-center gap-1.5 mb-3">
                  <Link2 className="size-3.5" />
                  {t("knowledge.backlinks")} ({backlinks.length})
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
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
            <FileText className="size-8 opacity-30" />
            <p className="text-sm">{t("knowledge.select_page")}</p>
          </div>
        )}
      </main>

      {/* Right Chat */}
      <div className="w-80 shrink-0 border-l border-border">
        <Chat />
      </div>
    </div>
  )
}

function Section({ title, items, selected, onSelect }: {
  title: string
  items: string[]
  selected: { type: string; name: string } | null
  onSelect: (name: string) => void
}) {
  const [collapsed, setCollapsed] = useState(false)
  if (items.length === 0) return null

  return (
    <div>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground w-full text-left px-2 py-1 rounded-md hover:bg-card/50 transition-colors"
      >
        {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
        {title}
        <span className="text-[9px] text-muted-foreground/50 ml-auto">{items.length}</span>
      </button>
      {!collapsed && (
        <div className="mt-0.5 space-y-0.5">
          {items.map(item => (
            <button
              key={item}
              onClick={() => onSelect(item)}
              className={cn(
                "block w-full text-left text-[11px] px-3 py-1.5 rounded-md transition-colors",
                selected?.name === item
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
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
