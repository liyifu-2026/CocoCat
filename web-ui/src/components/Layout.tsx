import { useState, useEffect, useCallback } from "react"
import { Outlet } from "react-router-dom"
import LeftNav from "./LeftNav"
import OpDisplay from "./OpDisplay"
import ChatPanel from "./chat/ChatPanel"
import { MobileBottomNav } from "./MobileBottomNav"
import { CommandPalette } from "./CommandPalette"

export default function Layout() {
  const [activeNav, setActiveNav] = useState("chat")
  const [paletteOpen, setPaletteOpen] = useState(false)

  const handleNavigate = useCallback((nav: string) => {
    setActiveNav(nav)
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
          <OpDisplay key={activeNav} activeNav={activeNav} />
          <ChatPanel />
        </>
      ) : (
        <OpDisplay key={activeNav} activeNav={activeNav} />
      )}

      <MobileBottomNav active={activeNav} onNavigate={handleNavigate} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onNavigate={(nav) => { handleNavigate(nav); setPaletteOpen(false) }} />
      <Outlet />
    </div>
  )
}
