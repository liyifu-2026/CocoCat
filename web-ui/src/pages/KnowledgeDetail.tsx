import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { knowledgeApi } from "@/api/knowledge"
import type { WikiPage } from "@/api/knowledge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft, ChevronRight, ChevronDown, Users, Lightbulb, BookOpen } from "lucide-react"
import { useT } from "@/context/LanguageContext"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { transformWikilinks } from "@/lib/wikilink-transform"
import { resolveWikiPage } from "@/lib/wiki-resolver"
import type { WikiPageInfo } from "@/lib/wiki-resolver"
import { FrontmatterPanel } from "@/components/FrontmatterPanel"

const TYPE_CONFIG: Record<string, { icon: typeof Users; labelKey: string; color: string }> = {
  entity:  { icon: Users,     labelKey: "knowledge.entities", color: "text-blue-500" },
  concept: { icon: Lightbulb, labelKey: "knowledge.concepts", color: "text-purple-500" },
  source:  { icon: BookOpen,  labelKey: "knowledge.sources",  color: "text-orange-500" },
}

export default function KnowledgeDetail() {
  const t = useT()
  const { kbId } = useParams<{ kbId: string }>()
  const { data: kb } = useQuery({
    queryKey: ["knowledge", kbId],
    queryFn: () => knowledgeApi.get(kbId!),
    enabled: !!kbId,
  })
  const { data: wiki } = useQuery({
    queryKey: ["knowledge", kbId, "wiki"],
    queryFn: () => knowledgeApi.listWiki(kbId!),
    enabled: !!kbId,
  })

  const [searchQuery, setSearchQuery] = useState("")

  const search = useQuery({
    queryKey: ["knowledge", kbId, "search", searchQuery],
    queryFn: () => knowledgeApi.search(kbId!, searchQuery),
    enabled: !!kbId && searchQuery.length >= 2,
  })

  const [selectedPage, setSelectedPage] = useState<string | null>(null)
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(["entity", "concept", "source"]))

  const pageContent = useQuery({
    queryKey: ["knowledge", kbId, "page", selectedPage],
    queryFn: async () => {
      if (!selectedPage || !kbId) return null
      const parts = selectedPage.split("/")
      const type = parts[parts.length - 2]!
      const name = parts[parts.length - 1]!
      return knowledgeApi.getWikiPage(kbId!, type, name)
    },
    enabled: !!selectedPage && !!kbId,
  })

  const grouped = new Map<string, WikiPage[]>()
  for (const page of wiki?.pages ?? []) {
    const list = grouped.get(page.type) ?? []
    list.push(page)
    grouped.set(page.type, list)
  }

  const sortedTypes = [...grouped.entries()].sort(([a], [b]) =>
    a.localeCompare(b)
  )

  const allPages: WikiPageInfo[] = (wiki?.pages ?? []).map(p => ({
    name: p.name,
    title: p.title,
    path: p.path,
  }))

  function toggleType(type: string) {
    setExpandedTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const pageContentData = pageContent.data

  function handleWikilinkClick(e: React.MouseEvent<HTMLAnchorElement>, href: string) {
    if (!href.startsWith("#")) return
    e.preventDefault()
    const slug = decodeURIComponent(href.slice(1))
    const resolved = resolveWikiPage(slug, allPages)
    if (resolved) setSelectedPage(resolved.path)
  }

  return (
    <div className="flex h-full">
      {/* Left sidebar: KB info + wiki tree */}
      <div className="w-64 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border">
          <Link
            to="/knowledge"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="size-3" /> {t("knowledge.back")}
          </Link>
          <h2 className="font-semibold truncate">{kbId}</h2>
        </div>
        <div className="p-2">
          <input
            type="text"
            placeholder={t("knowledge.search")}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring"
          />
        </div>
        {searchQuery.length >= 2 && search.data ? (
          <ScrollArea className="flex-1 p-2">
            <div className="text-xs font-medium text-muted-foreground px-2 pb-1">
              {t("knowledge.search_results").replace("{count}", String(search.data.results.length))}
            </div>
            {search.data.results.length === 0 && (
              <div className="px-2 text-xs text-muted-foreground">{t("knowledge.no_results")}</div>
            )}
            {search.data.results.map(r => (
              <button key={r.path}
                onClick={() => { setSelectedPage(r.path); setSearchQuery("") }}
                className="flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent/50">
                <span className="font-medium truncate">{r.title}</span>
                <span className="text-xs text-muted-foreground truncate">{r.snippet}</span>
              </button>
            ))}
          </ScrollArea>
        ) : (
          <ScrollArea className="flex-1 p-2">
            {kb?.purpose && (
              <div className="px-2 pb-3 text-xs text-muted-foreground border-b border-border mb-2">
                {kb.purpose.slice(0, 200)}
              </div>
            )}
            {sortedTypes.map(([type, pages]) => {
              const config = TYPE_CONFIG[type] ?? { icon: BookOpen, labelKey: type, color: "text-muted-foreground" }
              const Icon = config.icon
              const isExpanded = expandedTypes.has(type)
              return (
                <div key={type} className="mb-1">
                  <button
                    onClick={() => toggleType(type)}
                    className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent/50"
                  >
                    {isExpanded ? (
                      <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                    )}
                    <Icon className={`size-3.5 shrink-0 ${config.color}`} />
                    <span className="flex-1 text-left font-medium">{t(config.labelKey)}</span>
                    <span className="text-xs text-muted-foreground">{pages.length}</span>
                  </button>
                  {isExpanded && (
                    <div className="ml-3">
                      {pages.map(page => (
                        <button
                          key={page.name}
                          onClick={() => setSelectedPage(page.path)}
                          className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm ${
                            selectedPage === page.path
                              ? "bg-accent text-accent-foreground"
                              : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
                          }`}
                        >
                          <span className="truncate">{page.title || page.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </ScrollArea>
        )}
      </div>

      {/* Right: Wiki reader */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedPage && (
          <div className="text-center text-muted-foreground py-20">
            {t("knowledge.select_page")}
          </div>
        )}
        {pageContent.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}
        {pageContentData && (
          <div className="max-w-3xl mx-auto">
            {pageContentData.frontmatter && Object.keys(pageContentData.frontmatter).length > 0 && (
              <FrontmatterPanel frontmatter={pageContentData.frontmatter} />
            )}
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children, ...props }) => {
                    const h = typeof href === "string" ? href : ""
                    const isWikilink = h.startsWith("#")
                    return (
                      <a href={h || undefined}
                        onClick={(e) => isWikilink && handleWikilinkClick(e, h)}
                        className={isWikilink ? "cursor-pointer text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary" : "text-primary underline underline-offset-2"}
                        {...props}>
                        {children}
                      </a>
                    )
                  },
                }}
              >
                {transformWikilinks(pageContentData.body)}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
