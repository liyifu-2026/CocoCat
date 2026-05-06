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

  const handleNav = (to: string) => {
    if (collapsed) toggle()
    navigate(to)
  }

  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const scenes = data?.scenes ?? []

  const activeSceneId = location.pathname.match(/^\/scenes\/([^/]+)/)?.[1]

  return (
    <aside className="w-11 shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-2 gap-2">
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

      <nav className="flex-1 flex flex-col items-center gap-1.5 overflow-y-auto scrollbar-auto-hide">
        {scenes.map(scene => (
          <button
            key={scene.id}
            onClick={() => handleNav(`/scenes/${scene.id}`)}
            className={cn(
              "rounded-md transition-all duration-150",
              activeSceneId === scene.id
                ? "ring-2 ring-sidebar-primary ring-offset-1 ring-offset-sidebar"
                : "hover:opacity-80",
            )}
            title={scene.id}
          >
            <SceneAvatar id={scene.id} />
          </button>
        ))}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={openImportScene}
          className="mt-1 text-sidebar-foreground hover:bg-sidebar-accent"
          title="Import Scene"
        >
          <Plus className="size-4" />
        </Button>
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
