import { usePanel } from "@/context/PanelContext"
import { ScrollArea } from "@/components/ui/scroll-area"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export function PropertiesPanel() {
  const { content, visible, closePanel } = usePanel()

  if (!content) return null

  return (
    <aside
      className={cn(
        "hidden md:flex border-l border-border bg-card flex-col shrink-0 overflow-hidden h-full transition-[width,opacity] duration-200 ease-in-out",
        visible ? "w-80 opacity-100" : "w-0 opacity-0",
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-4 h-12 shrink-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Properties</span>
        <button
          onClick={closePanel}
          className="w-6 h-6 rounded flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <ScrollArea className="flex-1 p-4">
        {content}
      </ScrollArea>
    </aside>
  )
}
