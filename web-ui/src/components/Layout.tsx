import { useState } from "react"
import { Outlet } from "react-router-dom"
import { SceneRail } from "./SceneRail"
import { SettingsModal } from "./SettingsModal"
import { Settings } from "lucide-react"

export function Layout() {
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className="flex h-screen">
      <div className="flex flex-col items-center w-11 border-r py-2 gap-1 bg-muted/30">
        <SceneRail />
        <div className="flex-1" />
        <button
          onClick={() => setSettingsOpen(true)}
          className="p-1.5 rounded hover:bg-muted text-muted-foreground"
          title="Settings"
        >
          <Settings className="size-4" />
        </button>
      </div>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
