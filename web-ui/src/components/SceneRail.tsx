import { useState } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { scenesApi } from "@/api/scenes"
import { SceneAvatar } from "./SceneAvatar"
import { useTheme } from "@/context/ThemeContext"
import { useSidebar } from "@/context/SidebarContext"
import { useDialogActions } from "@/context/DialogContext"
import { Button } from "@/components/ui/button"
import { Sun, Moon, Plus, PanelRight } from "lucide-react"
import { cn } from "@/lib/utils"

export function SceneRail() {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  const { collapsed, toggle } = useSidebar()
  const { openImportScene } = useDialogActions()
  const [hovered, setHovered] = useState(false)

  const handleNav = (to: string) => {
    if (collapsed) toggle()
    navigate(to)
  }

  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const scenes = data?.scenes ?? []

  const activeSceneId = location.pathname.match(/^\/scenes\/([^/]+)/)?.[1]

  return (
    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-2 gap-2 transition-all duration-200 overflow-hidden ${
        hovered ? "w-32" : "w-11"
      }`}>
      <button
        onClick={() => handleNav("/dashboard")}
        className={cn(
          "w-7 h-7 rounded-md flex items-center justify-center transition-colors",
          location.pathname === "/dashboard" || location.pathname === "/"
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground hover:bg-sidebar-accent",
        )}
        title="Dashboard"
      >
        <span className="text-xs font-bold">CC</span>
      </button>
      {collapsed && (
        <button onClick={toggle} title="Show sidebar"
          className="w-7 h-7 rounded-md flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        >
          <PanelRight className="size-4" />
        </button>
      )}

      <div className="w-full border-t border-sidebar-border my-1" />

      <nav className="flex-1 flex flex-col items-center gap-1.5 overflow-y-auto scrollbar-auto-hide w-full px-1">
        {scenes.map(scene => (
          <button
            key={scene.id}
            onClick={() => handleNav(`/scenes/${scene.id}`)}
            className={`flex items-center gap-2 rounded-md transition-all duration-150 w-full px-1 ${
              activeSceneId === scene.id
                ? "ring-2 ring-sidebar-primary ring-offset-1 ring-offset-sidebar"
                : "hover:opacity-80"
            }`}
            title={hovered ? undefined : scene.id}
          >
            <SceneAvatar id={scene.id} />
            {hovered && <span className="text-xs text-sidebar-foreground truncate">{scene.id}</span>}
          </button>
        ))}
        <button
          onClick={openImportScene}
          className="flex items-center justify-center gap-2 w-full text-sidebar-foreground hover:bg-sidebar-accent rounded-md py-1 mt-1"
          title="Import / Create Scene"
        >
          <Plus className="size-4 shrink-0" />
          {hovered && <span className="text-xs">New Scene</span>}
        </button>
      </nav>

      <div className="w-full border-t border-sidebar-border my-1" />

      <button
        onClick={toggleTheme}
        className="w-7 h-7 rounded-md flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        title={theme === "light" ? "Dark Mode" : "Light Mode"}
      >
        {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
      </button>
    </aside>
  )
}
