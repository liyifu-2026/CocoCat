import { useState, useEffect } from "react"
import { useLiveUpdates } from "@/context/LiveUpdatesContext"

type VizState = "idle" | "active"

interface VizEvent {
  tool: string
  args: Record<string, unknown>
  status: "start" | "delta" | "end"
  data?: unknown
}

export default function VizEngine() {
  const [state, setState] = useState<VizState>("idle")
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const [output, setOutput] = useState<string>("")
  const { onMessage } = useLiveUpdates()

  useEffect(() => {
    const unsub = onMessage("tool_event", (data: Record<string, unknown>) => {
      const event = data as unknown as VizEvent

      switch (event.status) {
        case "start":
          setState("active")
          setCurrentTool(event.tool)
          setOutput("")
          break
        case "delta":
          if (typeof event.data === "string") {
            setOutput(prev => prev + event.data)
          }
          break
        case "end":
          setTimeout(() => {
            setState("idle")
            setCurrentTool(null)
          }, 3000)
          break
      }
    })

    return unsub
  }, [onMessage])

  if (state === "idle") return null

  return (
    <div className="px-4 pb-3">
      <div className="bg-card border border-accent/20 rounded-xl p-3 animate-scaleIn">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-accent animate-breathe" />
          <span className="text-[10px] font-medium text-accent">
            {currentTool || "Working"} · live
          </span>
        </div>
        {output && (
          <pre className="text-[10px] text-muted-foreground font-mono max-h-40 overflow-y-auto whitespace-pre-wrap">
            {output}
          </pre>
        )}
      </div>
    </div>
  )
}
