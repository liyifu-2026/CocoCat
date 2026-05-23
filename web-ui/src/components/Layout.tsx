import { useEffect, useRef, useCallback, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import LeftNav from "./LeftNav"
import ChatPanel from "./chat/ChatPanel"
import { MobileBottomNav } from "./MobileBottomNav"
import { CommandPalette } from "./CommandPalette"
import { useChatOverlay } from "@/context/ChatOverlayContext"
import { cn } from "@/lib/utils"
import { ChevronLeft, MessageSquare } from "lucide-react"
import { useMode } from "@/context/ModeContext"

export type QuickSendFn = (message: string) => void

export default function Layout() {
  const location = useLocation()
  const { chatState, setChatState } = useChatOverlay()
  const quickSendRef = useRef<QuickSendFn | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { currentMode } = useMode()

  const isChatRoute = location.pathname.startsWith("/chat")

  useEffect(() => {
    if (!isChatRoute && chatState === "overlay") {
      setChatState("collapsed")
    } else if (isChatRoute && chatState === "collapsed") {
      setChatState("overlay")
    }
  }, [location.pathname])

  const registerQuickSend = useCallback((fn: QuickSendFn) => {
    quickSendRef.current = fn
    return () => { quickSendRef.current = null }
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setPaletteOpen(true)
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "[") {
        e.preventDefault()
        setChatState("collapsed")
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "]") {
        e.preventDefault()
        setChatState("overlay")
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [setChatState])

  const isOverlay = chatState === "overlay"

  return (
    <div className="flex h-screen relative">
      <div className="bg-glow-blue" />
      <div className="bg-glow-amber" />

      <LeftNav />

      <div
        className={cn(
          "flex-1 flex flex-col overflow-hidden min-w-0 transition-[margin-right] duration-300 ease-out",
          isOverlay ? "mr-0" : "mr-[72px]"
        )}
      >
        <div className="flex-1 overflow-y-auto no-scrollbar">
          <Outlet />
        </div>
      </div>

      {/* ChatPanel: absolute overlay or fixed-width rail */}
      <div
        className={cn(
          "transition-all duration-300 ease-out shrink-0",
          isOverlay
            ? "w-[420px] absolute right-0 top-0 bottom-0 z-20"
            : "w-[72px] border-l border-sidebar-border bg-sidebar"
        )}
      >
        {isOverlay ? (
          <ChatPanel registerQuickSend={registerQuickSend} />
        ) : (
          <div className="h-full flex flex-col items-center py-4 gap-3">
            <button
              onClick={() => setChatState("overlay")}
              className="w-9 h-9 rounded-xl bg-card border border-border flex items-center justify-center hover:border-primary/30 transition-colors"
              title="Expand chat"
            >
              <ChevronLeft className="size-4 text-muted-foreground" />
            </button>
            <div className={cn(
              "w-9 h-9 rounded-full flex items-center justify-center text-sm",
              currentMode === "kb-admin"
                ? "bg-amber-500/10 text-amber-500"
                : "bg-blue-500/10 text-blue-500"
            )}>
              {currentMode === "kb-admin" ? "\u{1F4DA}" : "\u{1F4AC}"}
            </div>
            <div className="flex-1" />
            <div className="w-9 h-9 rounded-full bg-card border border-border flex items-center justify-center text-[10px] text-muted-foreground">
              <MessageSquare className="size-4" />
            </div>
          </div>
        )}
      </div>

      <MobileBottomNav />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}
