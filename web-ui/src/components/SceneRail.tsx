import { useState } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

import { SceneAvatar } from "./SceneAvatar"
import { useTheme } from "@/context/ThemeContext"
import { useSidebar } from "@/context/SidebarContext"
import { useT } from "@/context/LanguageContext"
import { useDialogActions } from "@/context/DialogContext"
import { Button } from "@/components/ui/button"
import { Sun, Moon, Plus, PanelRight } from "lucide-react"
import { cn } from "@/lib/utils"

export function SceneRail() {
  const t = useT()
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

  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => fetch("/api/scenes").then(r => r.json()) })
  const scenes: any[] = (data as any)?.scenes ?? []

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
        title={t("component.dashboard")}
      >
        <span className="text-xs font-bold">CC</span>
      </button>
      {collapsed && (
        <button onClick={toggle} title={t("component.show_sidebar")}
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
          title={t("import_create.title")}
        >
          <Plus className="size-4 shrink-0" />
          {hovered && <span className="text-xs">{t("component.new_scene")}</span>}
        </button>
      </nav>

      <div className="w-full border-t border-sidebar-border my-1" />

      <button
        onClick={toggleTheme}
        className="w-7 h-7 rounded-md flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        title={theme === "light" ? t("component.dark_mode") : t("component.light_mode")}
      >
        {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
      </button>
    </aside>
  )
}
