import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import { Brain } from "lucide-react"

export default function MemoryPage() {
  return (
    <>
      <Namecard />
      <VizEngine />
      <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
        <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
          <Brain className="size-6 text-muted-foreground/40" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-foreground mb-1">Memory Timeline</h3>
          <p className="text-[11px] text-muted-foreground max-w-[240px]">
            Pinned facts and conversation memory will appear here. Use chat to build context.
          </p>
        </div>
      </div>
    </>
  )
}
