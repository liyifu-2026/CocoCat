import { useRef, useCallback, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import SearchPanel from "./SearchPanel"
import { ChevronDown } from "lucide-react"

const COVER_COLORS: { bg: string }[] = [
  { bg: "bg-gradient-to-br from-blue-700 to-blue-900" },
  { bg: "bg-gradient-to-br from-indigo-700 to-indigo-900" },
  { bg: "bg-gradient-to-br from-cyan-700 to-cyan-900" },
  { bg: "bg-gradient-to-br from-amber-700 to-amber-900" },
  { bg: "bg-gradient-to-br from-rose-700 to-rose-900" },
  { bg: "bg-gradient-to-br from-emerald-700 to-emerald-900" },
  { bg: "bg-gradient-to-br from-violet-700 to-violet-900" },
  { bg: "bg-gradient-to-br from-sky-700 to-sky-900" },
]

interface KbInfo { id: string; purpose?: string }

const BOOK_WIDTH = 80

interface Props {
  selectedKb: string | null
  onSelect: (kbName: string) => void
}

export default function Bookshelf({ selectedKb, onSelect }: Props) {
  const shelfRef = useRef<HTMLDivElement>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const navigate = useNavigate()
  const t = useT()

  const { data } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const kbs: KbInfo[] = (data as any)?.kbs ?? []
  const totalWidth = kbs.length * BOOK_WIDTH

  useEffect(() => {
    if (!selectedKb || !shelfRef.current) return
    const idx = kbs.findIndex(k => k.id === selectedKb)
    if (idx < 0) return
    shelfRef.current.scrollLeft = idx * BOOK_WIDTH - shelfRef.current.clientWidth / 2 + BOOK_WIDTH / 2
  }, [selectedKb, kbs])

  const handleScroll = useCallback(() => {
    if (!shelfRef.current) return
    const el = shelfRef.current
    const center = el.scrollLeft + el.clientWidth / 2
    const idx = Math.round(center / BOOK_WIDTH)
    if (idx < 0 || idx >= kbs.length) return
    if (kbs[idx] && kbs[idx].id !== selectedKb) {
      onSelect(kbs[idx].id)
    }
  }, [kbs, selectedKb, onSelect])

  const handleBookClick = (kbName: string) => {
    onSelect(kbName)
    navigate(`/knowledge/${kbName}`)
  }

  const handleSearchSelect = (kbName: string) => {
    onSelect(kbName)
    navigate(`/knowledge/${kbName}`)
    setSearchOpen(false)
  }

  if (kbs.length === 0) {
    return (
      <div className="h-[120px] flex items-center justify-center">
        <p className="text-[11px] text-muted-foreground/40">{t("knowledge.no_kbs")}</p>
      </div>
    )
  }

  return (
    <div className="relative h-[120px] select-none">
      <button
        onClick={() => setSearchOpen(true)}
        className="absolute top-0 left-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-card border border-border shadow-md hover:border-primary/40 transition-colors cursor-pointer"
        style={{ transform: "translateX(-50%)" }}
        title="Search knowledge bases"
      >
        <ChevronDown className="size-4 text-primary" />
      </button>

      <div
        ref={shelfRef}
        className="overflow-x-auto no-scrollbar snap-x snap-mandatory pt-10 pb-2"
        onScroll={handleScroll}
      >
        <div className="flex" style={{ minWidth: "100%" }}>
          <div className="shrink-0" style={{ width: "calc(50vw - 38px - 36px - 40px)" }} />

          {kbs.map((kb, i) => {
            const color = COVER_COLORS[i % COVER_COLORS.length]!
            const isSelected = kb.id === selectedKb
            return (
              <div
                key={kb.id}
                className={cn(
                  "shrink-0 snap-center cursor-pointer transition-all duration-200",
                  isSelected ? "scale-110 z-10" : "hover:scale-105"
                )}
                style={{ width: BOOK_WIDTH }}
                onClick={() => handleBookClick(kb.id)}
              >
                <div
                  className={cn(
                    "h-20 rounded-lg relative overflow-hidden shadow-md flex flex-col justify-end p-1.5",
                    color.bg,
                    isSelected && "ring-2 ring-primary ring-offset-2 ring-offset-background"
                  )}
                >
                  <h5 className="text-[8px] font-bold text-white/90 truncate">{kb.id}</h5>
                </div>
              </div>
            )
          })}

          <div className="shrink-0 snap-center cursor-pointer" style={{ width: BOOK_WIDTH }}
            onClick={() => navigate("/settings/kb")}
          >
            <div className="h-20 rounded-lg border-2 border-dashed border-border flex items-center justify-center hover:border-primary/30 transition-colors">
              <span className="text-muted-foreground/40 text-lg">+</span>
            </div>
          </div>

          <div className="shrink-0" style={{ width: "calc(50vw - 38px - 36px - 40px)" }} />
        </div>
      </div>

      {searchOpen && (
        <SearchPanel
          kbs={kbs}
          onSelect={handleSearchSelect}
          onClose={() => setSearchOpen(false)}
        />
      )}
    </div>
  )
}
