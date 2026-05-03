import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { knowledgeApi } from "@/api/knowledge"
import type { WikiPage } from "@/api/knowledge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft, ChevronRight, ChevronDown, Users, Lightbulb, BookOpen } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const TYPE_CONFIG: Record<string, { icon: typeof Users; label: string; color: string }> = {
  entity:  { icon: Users,     label: "Entities", color: "text-blue-500" },
  concept: { icon: Lightbulb, label: "Concepts", color: "text-purple-500" },
  source:  { icon: BookOpen,  label: "Sources",  color: "text-orange-500" },
}

export default function KnowledgeDetail() {
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

  function toggleType(type: string) {
    setExpandedTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const pageContentData = pageContent.data

  return (
    <div className="flex h-full">
      {/* Left sidebar: KB info + wiki tree */}
      <div className="w-64 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border">
          <Link
            to="/knowledge"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="size-3" /> Back
          </Link>
          <h2 className="font-semibold truncate">{kbId}</h2>
        </div>
        <ScrollArea className="flex-1 p-2">
          {kb?.purpose && (
            <div className="px-2 pb-3 text-xs text-muted-foreground border-b border-border mb-2">
              {kb.purpose.slice(0, 200)}
            </div>
          )}
          {sortedTypes.map(([type, pages]) => {
            const config = TYPE_CONFIG[type] ?? { icon: BookOpen, label: type, color: "text-muted-foreground" }
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
                  <span className="flex-1 text-left font-medium">{config.label}</span>
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
      </div>

      {/* Right: Wiki reader */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedPage && (
          <div className="text-center text-muted-foreground py-20">
            Select a wiki page from the sidebar
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
            {pageContentData.frontmatter?.title && (
              <h1 className="text-2xl font-bold mb-4">{pageContentData.frontmatter.title}</h1>
            )}
            <div className="flex flex-wrap gap-1 mb-4">
              {pageContentData.frontmatter?.type && (
                <Badge variant="outline">{pageContentData.frontmatter.type}</Badge>
              )}
              {pageContentData.frontmatter?.tags
                ?.split(",")
                .map((t: string, i: number) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {t.trim()}
                  </Badge>
                ))}
            </div>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {pageContentData.body}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
