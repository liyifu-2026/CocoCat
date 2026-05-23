import { Users, Lightbulb, BookOpen, FileText, Calendar, ArrowUpRight, Layers, Tag } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useT } from "@/context/LanguageContext"

const TYPE_CONFIG: Record<string, { icon: typeof Users; labelKey: string; color: string }> = {
  entity:    { icon: Users,     labelKey: "frontmatter.entity",    color: "text-blue-500" },
  concept:   { icon: Lightbulb, labelKey: "frontmatter.concept",   color: "text-purple-500" },
  source:    { icon: BookOpen,  labelKey: "frontmatter.source",    color: "text-orange-500" },
  query:     { icon: FileText,  labelKey: "frontmatter.query",     color: "text-green-500" },
}

interface FrontmatterPanelProps {
  frontmatter: Record<string, string>
}

export function FrontmatterPanel({ frontmatter }: FrontmatterPanelProps) {
  const t = useT()
  const type = frontmatter.type?.toLowerCase() ?? ""
  const typeStyle = TYPE_CONFIG[type] ?? { icon: FileText, labelKey: "frontmatter.page", color: "text-muted-foreground" }
  const TypeIcon = typeStyle.icon
  const tags = frontmatter.tags?.split(",").map(t => t.trim()).filter(Boolean) ?? []
  const sources = frontmatter.sources?.split(",").map(s => s.trim()).filter(Boolean) ?? []
  const related = frontmatter.related?.split(",").map(r => r.trim()).filter(Boolean) ?? []

  return (
    <div className="mb-6 rounded-xl border border-border/60 bg-muted/20 p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted ${typeStyle.color}`}>
          <TypeIcon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          {frontmatter.title && (
            <div className="text-base font-semibold">{frontmatter.title}</div>
          )}
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            <Badge variant="outline" className="text-xs">{t(typeStyle.labelKey)}</Badge>
            {frontmatter.created && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Calendar className="size-3" /> {frontmatter.created}
              </span>
            )}
            {tags.map((tag, i) => (
              <span key={i} className="inline-flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                <Tag className="size-3" /> {tag}
              </span>
            ))}
          </div>
        </div>
      </div>

      {frontmatter.description && (
        <p className="text-sm italic text-muted-foreground">{frontmatter.description}</p>
      )}

      {frontmatter.origin && (
        <div className="rounded border-l-2 border-primary/40 bg-primary/5 px-3 py-1.5 text-xs text-foreground/80">
          <span className="font-medium text-muted-foreground">{t("frontmatter.origin")} </span>{frontmatter.origin}
        </div>
      )}

      {sources.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
            <Layers className="size-3" /> {t("frontmatter.sources")} ({sources.length})
          </div>
          <div className="flex flex-wrap gap-1">
            {sources.map((s, i) => (
              <span key={i} className="rounded-md border border-border/60 bg-background px-2 py-0.5 text-xs">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {related.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
            <ArrowUpRight className="size-3" /> {t("frontmatter.related")}
          </div>
          <div className="flex flex-wrap gap-1">
            {related.map((r, i) => (
              <span key={i} className="inline-flex items-center gap-0.5 rounded-full border border-border/60 bg-background px-2 py-0.5 text-xs cursor-pointer hover:bg-accent">
                {r} <ArrowUpRight className="size-2.5" />
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
