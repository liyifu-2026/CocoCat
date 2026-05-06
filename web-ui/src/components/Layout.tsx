import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { SceneRail } from "./SceneRail"
import { CommandPalette } from "./CommandPalette"
import { KeyboardShortcuts } from "./KeyboardShortcuts"
import { ImportSceneDialog } from "./ImportSceneDialog"
import { NewSceneDialog } from "./NewSceneDialog"

export function Layout() {
  return (
    <div className="flex h-full">
      <SceneRail />
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <CommandPalette />
      <KeyboardShortcuts />
      <ImportSceneDialog />
      <NewSceneDialog />
    </div>
  )
}
