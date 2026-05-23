import { useState, useEffect, useRef } from "react"
import { Search, X } from "lucide-react"

interface KbInfo { id: string; purpose?: string }

interface Props {
  kbs: KbInfo[]
  onSelect: (kbName: string) => void
  onClose: () => void
}

export default function SearchPanel({ kbs, onSelect, onClose }: Props) {
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [onClose])

  const filtered = query
    ? kbs.filter(k => k.id.toLowerCase().includes(query.toLowerCase()))
    : kbs

  return (
    <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 w-64 bg-popover border border-border rounded-xl shadow-xl p-3 space-y-2 animate-scaleIn">
      <div className="flex items-center gap-2 bg-input border border-border rounded-lg px-3 py-1.5">
        <Search className="size-3.5 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search KB..."
          className="flex-1 bg-transparent border-none outline-none text-xs text-foreground placeholder:text-muted-foreground/40"
        />
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto space-y-0.5">
        {filtered.map(kb => (
          <button
            key={kb.id}
            onClick={() => onSelect(kb.id)}
            className="w-full text-left px-3 py-2 rounded-lg text-xs hover:bg-muted transition-colors flex flex-col"
          >
            <span className="font-medium text-foreground">{kb.id}</span>
            {kb.purpose && <span className="text-[9px] text-muted-foreground truncate">{kb.purpose}</span>}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-center text-[10px] text-muted-foreground py-4">No matches</p>
        )}
      </div>
    </div>
  )
}
