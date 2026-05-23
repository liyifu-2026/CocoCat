import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { BookOpen, Search, ChevronRight, ChevronDown, FileText, X } from "lucide-react"
import { MermaidBlock } from "@/components/MermaidBlock"

interface WikiItem {
  name: string
  url?: string
  description?: string
}

interface WikiData {
  entities?: WikiItem[]
  concepts?: WikiItem[]
  pages?: WikiItem[]
}

interface Props {
  kbName: string | null
}

export default function DocRenderer({ kbName }: Props) {
  const navigate = useNavigate()
  const { pageType, pageName } = useParams()
  const t = useT()
  const [searchQuery, setSearchQuery] = useState("")

  const { data: wikiData } = useQuery({
    queryKey: ["wiki", kbName],
    queryFn: () => fetch(`/api/knowledge/${kbName}/wiki`).then(r => r.json()),
    enabled: !!kbName,
  })

  const wiki = (wikiData as WikiData) || {}
  const entities = (wiki.entities || []) as WikiItem[]
  const concepts = (wiki.concepts || []) as WikiItem[]
  const pages = (wiki.pages || []) as WikiItem[]

  const { data: pageData, isLoading: pageLoading } = useQuery({
    queryKey: ["wiki-page", kbName, pageType, pageName],
    queryFn: () => fetch(`/api/knowledge/${kbName}/wiki/${pageType}/${pageName}`).then(r => r.json()),
    enabled: !!kbName && !!pageType && !!pageName,
  })

  const filterBySearch = (items: WikiItem[]) => {
    if (!searchQuery) return items
    const q = searchQuery.toLowerCase()
    return items.filter(item =>
      item.name.toLowerCase().includes(q) ||
      (item.description && item.description.toLowerCase().includes(q))
    )
  }

  const allFiltered = {
    entities: filterBySearch(entities),
    concepts: filterBySearch(concepts),
    pages: filterBySearch(pages),
  }

  const handleWikiClick = (item: WikiItem, section: string) => {
    navigate(`/knowledge/${kbName}/${section}/${item.name}`)
  }

  if (!kbName) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground/40">
        <div className="text-center">
          <BookOpen className="size-8 mx-auto mb-2 opacity-30" />
          <p className="text-xs">Select a knowledge base to browse</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="w-[220px] border-r border-border overflow-y-auto no-scrollbar p-3 space-y-3 shrink-0">
        <div className="flex items-center gap-2 bg-input border border-border rounded-lg px-2.5 py-1.5">
          <Search className="size-3 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder={t("knowledge.search_wiki")}
            className="flex-1 bg-transparent border-none outline-none text-[10px] text-foreground placeholder:text-muted-foreground/40"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="text-muted-foreground">
              <X className="size-3" />
            </button>
          )}
        </div>

        <WikiSection title="Entities" items={allFiltered.entities} activePage={`${pageType}/${pageName}`} section="entities" onSelect={handleWikiClick} />
        <WikiSection title="Concepts" items={allFiltered.concepts} activePage={`${pageType}/${pageName}`} section="concepts" onSelect={handleWikiClick} />
        <WikiSection title="Pages" items={allFiltered.pages} activePage={`${pageType}/${pageName}`} section="pages" onSelect={handleWikiClick} />
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {pageLoading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-6 w-1/3 bg-muted rounded" />
            <div className="h-4 w-full bg-muted rounded" />
            <div className="h-4 w-3/4 bg-muted rounded" />
          </div>
        ) : pageData ? (
          <div className="markdown-content text-sm">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre: ({ children }) => <>{children}</>,
                code: ({ className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || "")
                  const isMermaid = match && match[1] === "mermaid"
                  if (isMermaid) {
                    try {
                      return <MermaidBlock code={String(children)} />
                    } catch {
                      return <pre className="bg-muted rounded-lg p-4 overflow-x-auto text-xs"><code>{children}</code></pre>
                    }
                  }
                  const isInline = !match && !String(children).includes("\n")
                  if (isInline) return <code className={className} {...props}>{children}</code>
                  return (
                    <pre className="bg-muted rounded-lg p-4 overflow-x-auto text-xs">
                      <code className={className} {...props}>{children}</code>
                    </pre>
                  )
                },
              }}
            >
              {typeof (pageData as any)?.content === "string"
                ? (pageData as any).content
                : (pageData as any)?.markdown || JSON.stringify(pageData)}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground/40">
            <div className="text-center">
              <FileText className="size-8 mx-auto mb-2 opacity-30" />
              <p className="text-xs">{t("knowledge.select_page")}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function WikiSection({
  title, items, activePage, section, onSelect,
}: {
  title: string
  items: WikiItem[]
  activePage: string
  section: string
  onSelect: (item: WikiItem, section: string) => void
}) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 hover:text-foreground transition-colors"
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        {title} ({items.length})
      </button>
      {expanded && (
        <div className="space-y-0.5 pl-1">
          {items.map(item => {
            const isActive = `${section}/${item.name}` === activePage
            return (
              <button
                key={item.name}
                onClick={() => onSelect(item, section)}
                className={cn(
                  "w-full text-left px-2.5 py-1.5 rounded-md text-[10px] transition-colors truncate",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {item.name}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
