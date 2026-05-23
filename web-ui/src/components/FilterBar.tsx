import { Search, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useT } from "@/context/LanguageContext"

interface FilterOption {
  key: string
  label: string
  active?: boolean
}

interface FilterBarProps {
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
  filters?: FilterOption[]
  onFilterToggle?: (key: string) => void
}

export function FilterBar({ search, onSearchChange, searchPlaceholder, filters, onFilterToggle }: FilterBarProps) {
  const t = useT()
  const placeholder = searchPlaceholder ?? t("filter.search_placeholder")
  return (
    <div className="flex items-center gap-2">
      <div className="relative flex-1 max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground/50" />
        <Input
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          placeholder={placeholder}
          className="pl-8 h-9 text-sm rounded-xl border-border/60 bg-background/80 focus:bg-background transition-all duration-200"
        />
      </div>
      {filters && onFilterToggle && (
        <div className="flex gap-1">
          {filters.map(f => (
              <Badge
                key={f.key}
                variant={f.active ? "default" : "outline"}
                className="cursor-pointer select-none gap-1"
                onClick={() => onFilterToggle(f.key)}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onFilterToggle(f.key) } }}
                tabIndex={0}
                role="button"
              >
              {f.label}
              {f.active && <X className="size-3" onClick={(e) => { e.stopPropagation(); onFilterToggle(f.key) }} />}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
