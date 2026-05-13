import { useState } from "react"
import { Outlet } from "react-router-dom"
import { SceneRail } from "./SceneRail"
import { SettingsModal } from "./SettingsModal"

export function Layout() {
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className="flex h-screen relative">
      <div className="bg-warm-glow" />
      <div className="bg-warm-glow-left" />
      <div className="bg-noise" />
      <SceneRail onOpenSettings={() => setSettingsOpen(true)} />
      <main className="flex-1 overflow-hidden relative z-10">
        <Outlet />
      </main>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
