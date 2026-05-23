import { useState, useEffect, useCallback, useRef } from "react"
import { Outlet } from "react-router-dom"
import LeftNav from "./LeftNav"
import OpDisplay from "./OpDisplay"
import ChatPanel from "./chat/ChatPanel"
import { MobileBottomNav } from "./MobileBottomNav"
import { CommandPalette } from "./CommandPalette"

export type QuickSendFn = (message: string) => void

export default function Layout() {
  const [activeNav, setActiveNav] = useState("chat")
  const [paletteOpen, setPaletteOpen] = useState(false)
  const quickSendRef = useRef<QuickSendFn | null>(null)

  const handleNavigate = useCallback((nav: string) => {
    setActiveNav(nav)
  }, [])

  const handleQuickSend = useCallback((message: string) => {
    setActiveNav("chat")
    setTimeout(() => {
      quickSendRef.current?.(message)
    }, 50)
  }, [])

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
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [])

  return (
    <div className="flex h-screen relative">
      <div className="bg-glow-blue" />
      <div className="bg-glow-amber" />

      <LeftNav active={activeNav} onNavigate={handleNavigate} />

      {activeNav === "chat" ? (
        <>
          <OpDisplay key={activeNav} activeNav={activeNav} onQuickSend={handleQuickSend} />
          <ChatPanel registerQuickSend={registerQuickSend} />
        </>
      ) : (
        <OpDisplay key={activeNav} activeNav={activeNav} onQuickSend={handleQuickSend} />
      )}

      <MobileBottomNav active={activeNav} onNavigate={handleNavigate} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onNavigate={(nav) => { handleNavigate(nav); setPaletteOpen(false) }} />
      <Outlet />
    </div>
  )
}
