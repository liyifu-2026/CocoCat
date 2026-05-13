import { useState } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

import { SceneAvatar } from "./SceneAvatar"
import { useTheme } from "@/context/ThemeContext"
import { useSidebar } from "@/context/SidebarContext"
import { useT } from "@/context/LanguageContext"
import { useDialogActions } from "@/context/DialogContext"
import { Sun, Moon, Plus, PanelRight, Settings, GitBranch } from "lucide-react"
import { cn } from "@/lib/utils"

interface SceneRailProps {
  onOpenSettings: () => void
}

export function SceneRail({ onOpenSettings }: SceneRailProps) {
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
  const scenes: { id: string }[] = (data as { scenes: { id: string }[] })?.scenes ?? []

  const activeSceneId = location.pathname.match(/^\/scenes\/([^/]+)/)?.[1]

  return (
    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-3 gap-2 overflow-hidden z-20 transition-all duration-300 ease-out",
        hovered ? "w-36" : "w-13",
      )}
    >
      <button
        onClick={() => handleNav("/dashboard")}
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
          location.pathname === "/dashboard" || location.pathname === "/"
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-sidebar-foreground hover:bg-sidebar-accent",
        )}
        title={t("component.dashboard")}
          aria-label={t("component.dashboard")}
      >
        <span className="text-xs font-display font-bold tracking-wider" style={hovered ? {} : {}}>Cc</span>
      </button>
      {collapsed && (
        <button onClick={toggle} title={t("component.show_sidebar")}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-all duration-200"
        >
          <PanelRight className="size-4" />
        </button>
      )}

      <div className="w-6 border-t border-sidebar-border my-0.5" />

      <nav className="flex-1 flex flex-col items-center gap-1.5 overflow-y-auto w-full px-1.5">
        {scenes.map((scene, i) => (
          <button
            key={scene.id}
            onClick={() => handleNav(`/scenes/${scene.id}`)}
            className={cn(
              "flex items-center gap-2.5 rounded-lg transition-all duration-200 w-full px-1.5 py-1 stagger-1",
              activeSceneId === scene.id
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50",
            )}
            title={hovered ? undefined : scene.id}
            style={{ animationDelay: `${i * 0.04}s` }}
          >
            <SceneAvatar id={scene.id} size={activeSceneId === scene.id ? "md" : "sm"} />
            {hovered && <span className="text-xs text-sidebar-foreground truncate font-medium">{scene.id}</span>}
          </button>
        ))}
        <button
          onClick={openImportScene}
          className="flex items-center justify-center gap-2 w-full text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent rounded-lg py-1.5 mt-0.5 transition-all duration-200"
          title={t("import_create.title")}
        >
          <Plus className="size-4 shrink-0" />
          {hovered && <span className="text-xs">{t("component.new_scene")}</span>}
        </button>
      </nav>

      <div className="w-6 border-t border-sidebar-border my-0.5" />

      <div className="flex flex-col items-center gap-1.5">
        <button
          onClick={() => handleNav("/dag")}
          className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
            location.pathname === "/dag"
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent",
          )}
          title="DAG"
        >
          <GitBranch className="size-4" />
        </button>
        <button
          onClick={toggleTheme}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-all duration-200"
          title={theme === "light" ? t("component.dark_mode") : t("component.light_mode")}
        >
          {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
        </button>
        <button
          onClick={onOpenSettings}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-all duration-200"
          title="Settings"
        >
          <Settings className="size-4" />
        </button>
      </div>
    </aside>
  )
}