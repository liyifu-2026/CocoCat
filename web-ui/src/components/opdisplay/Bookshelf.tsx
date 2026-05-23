import { useState, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"

const COVER_COLORS: { bg: string; accent: string; pattern: string }[] = [
  { bg: "bg-gradient-to-br from-blue-700 to-blue-900", accent: "#93c5fd", pattern: "circle" },
  { bg: "bg-gradient-to-br from-indigo-700 to-indigo-900", accent: "#a5b4fc", pattern: "diamond" },
  { bg: "bg-gradient-to-br from-cyan-700 to-cyan-900", accent: "#67e8f9", pattern: "wave" },
  { bg: "bg-gradient-to-br from-amber-700 to-amber-900", accent: "#fcd34d", pattern: "cross" },
  { bg: "bg-gradient-to-br from-rose-700 to-rose-900", accent: "#fda4af", pattern: "lines" },
  { bg: "bg-gradient-to-br from-emerald-700 to-emerald-900", accent: "#6ee7b7", pattern: "circle" },
  { bg: "bg-gradient-to-br from-violet-700 to-violet-900", accent: "#c4b5fd", pattern: "diamond" },
  { bg: "bg-gradient-to-br from-sky-700 to-sky-900", accent: "#bae6fd", pattern: "wave" },
]

function CoverPattern({ type, accent }: { type: string; accent: string }) {
  return (
    <svg className="absolute inset-0 w-full h-full opacity-30 pointer-events-none" viewBox="0 0 100 150" fill="none" stroke={accent} strokeWidth="0.6">
      {type === "circle" && (
        <>
          <circle cx="50" cy="70" r="22" />
          <circle cx="50" cy="70" r="13" />
          <line x1="50" y1="30" x2="50" y2="110" />
          <path d="M44,70 L56,70 M50,64 L50,76" strokeWidth="0.8" />
        </>
      )}
      {type === "diamond" && (
        <>
          <path d="M20,40 L80,40 L50,110 Z" />
          <path d="M30,52 L70,52 L50,98 Z" />
        </>
      )}
      {type === "wave" && (
        <path d="M10,80 C30,50 50,110 70,70 C80,50 95,60 100,55" strokeWidth="0.8" />
      )}
      {type === "cross" && (
        <>
          <line x1="30" y1="40" x2="70" y2="80" />
          <line x1="70" y1="40" x2="30" y2="80" />
        </>
      )}
      {type === "lines" && (
        <>
          <line x1="25" y1="45" x2="75" y2="45" />
          <line x1="25" y1="60" x2="75" y2="60" />
          <line x1="25" y1="75" x2="60" y2="75" />
        </>
      )}
    </svg>
  )
}

function BookCover({ kb, index }: { kb: { id: string; purpose?: string }; index: number }) {
  const c = COVER_COLORS[index % COVER_COLORS.length]!
  return (
    <div className={cn("h-44 rounded-2xl relative shadow-md overflow-hidden flex flex-col justify-between p-3.5 group-hover:shadow-lg transition-shadow", c.bg)}>
      <CoverPattern type={c.pattern} accent={c.accent} />
      <div className="self-end w-5 h-5 rounded-full border border-white/15 flex items-center justify-center text-[9px] z-10 shrink-0 text-white/80">📚</div>
      <div className="space-y-0.5 z-10">
        <h4 className="text-[10px] font-bold leading-tight text-white/95 line-clamp-2">{kb.id}</h4>
        {kb.purpose && <p className="text-[7px] text-white/60 truncate">{kb.purpose}</p>}
      </div>
      <span className="bookmark-ribbon absolute bottom-0 left-[20%] w-[10px] h-[18px] rounded-b-sm shadow-sm z-20" style={{ backgroundColor: c.accent }} />
    </div>
  )
}

export default function Bookshelf() {
  const shelfRef = useRef<HTMLDivElement>(null)
  const [activeCategory, setActiveCategory] = useState("all")
  const t = useT()

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const kbs = (data as any)?.kbs ?? []

  const scroll = (dir: "left" | "right") => {
    shelfRef.current?.scrollBy({ left: dir === "left" ? -200 : 200, behavior: "smooth" })
  }

  return (
    <div className="p-4 space-y-4 animate-view-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-foreground tracking-wide">{t("knowledge.title")}</h2>
          <p className="text-[9px] text-muted-foreground mt-0.5">{kbs.length} books on shelf</p>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => scroll("left")} className="p-1.5 rounded-lg bg-card border border-border hover:bg-muted text-muted-foreground transition-colors">
            <ChevronLeft className="size-3.5" />
          </button>
          <button onClick={() => scroll("right")} className="p-1.5 rounded-lg bg-card border border-border hover:bg-muted text-muted-foreground transition-colors">
            <ChevronRight className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Category pills */}
      <div className="overflow-x-auto no-scrollbar flex items-center gap-2 py-1">
        {["all", "recent", "large", "archived"].map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all shrink-0",
              activeCategory === cat
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-card border border-border text-muted-foreground hover:text-foreground"
            )}
          >
            {cat === "all" ? "All" : cat === "recent" ? "Recent" : cat === "large" ? "Large" : "Archived"}
          </button>
        ))}
      </div>

      {/* Bookshelf */}
      {isLoading ? (
        <div className="flex gap-3 overflow-hidden">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="shrink-0 w-[130px]">
              <div className="h-44 rounded-2xl bg-card shimmer-skeleton" />
              <div className="mt-2 space-y-1 px-1">
                <div className="h-3 w-3/4 rounded shimmer-skeleton" />
                <div className="h-2.5 w-1/2 rounded shimmer-skeleton" />
              </div>
            </div>
          ))}
        </div>
      ) : kbs.length === 0 ? (
        <div className="py-10 text-center">
          <p className="text-[11px] text-muted-foreground/50">{t("knowledge.no_kb_desc")}</p>
        </div>
      ) : (
        <div ref={shelfRef} className="flex gap-3 overflow-x-auto no-scrollbar scroll-smooth pb-2">
          {kbs.map((kb: any, i: number) => (
            <div key={kb.id} className="book-card shrink-0 w-[130px] cursor-pointer group transition-all duration-300 hover:-translate-y-1">
              <BookCover kb={kb} index={i} />
              <div className="mt-2 space-y-0.5 px-1">
                <h5 className="text-[10px] font-semibold text-foreground truncate leading-tight">{kb.id}</h5>
                {kb.purpose && <p className="text-[8px] text-muted-foreground truncate">{kb.purpose}</p>}
              </div>
            </div>
          ))}
          {/* Add new shelf placeholder */}
          <div className="shrink-0 w-[130px] flex flex-col items-center justify-center border-2 border-dashed border-border rounded-2xl h-44 cursor-pointer hover:border-primary/30 transition-colors group">
            <span className="text-muted-foreground/30 text-2xl group-hover:text-primary/40 transition-colors">+</span>
            <span className="text-[8px] text-muted-foreground/40 mt-1">New KB</span>
          </div>
        </div>
      )}
    </div>
  )
}
