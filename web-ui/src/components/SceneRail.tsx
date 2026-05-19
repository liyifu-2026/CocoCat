import { useState } from "react"
import { useLocation, NavLink } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

import { SceneAvatar } from "./SceneAvatar"
import { useTheme } from "@/context/ThemeContext"
import { useSidebar } from "@/context/SidebarContext"
import { useT } from "@/context/LanguageContext"
import { Sun, Moon, Plus, PanelRight, Settings, Layers, Bot, Book, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"

interface SceneRailProps {
  onOpenSettings: () => void
}

export function SceneRail({ onOpenSettings }: SceneRailProps) {
  const t = useT()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  const { collapsed, toggle } = useSidebar()
  
  const [hovered, setHovered] = useState(false)

  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => fetch("/api/scenes").then(r => r.json()) })
  const scenes: { id: string; name: string; status: string }[] = Array.isArray(data)
    ? data
    : (data as { scenes: { id: string; name: string; status: string }[] })?.scenes ?? []

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
      <NavLink
        to="/dashboard"
        onClick={() => { if (collapsed) toggle() }}
        className={({ isActive }) => cn(
          "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
          isActive
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-sidebar-foreground hover:bg-sidebar-accent",
        )}
        title={t("component.dashboard")}
        aria-label={t("component.dashboard")}
      >
        <img src="/app/logo.png" alt="CocoCat" className="w-8 h-8 object-contain" />
      </NavLink>
      {collapsed && (
        <button onClick={toggle} title={t("component.show_sidebar")}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-all duration-200"
        >
          <PanelRight className="size-4" />
        </button>
      )}

      <NavLink
        to="/chat"
        onClick={() => { if (collapsed) toggle() }}
        className={({ isActive }) => cn(
          "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
          isActive
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent",
        )}
        title={t("nav.chat")}
      >
        <MessageSquare className="size-4" />
      </NavLink>

      <div className="w-6 border-t border-sidebar-border my-0.5" />

      <nav className="flex-1 flex flex-col items-center gap-1.5 overflow-y-auto w-full px-1.5">
        {scenes.map((scene, i) => {
          const statusColors: Record<string, string> = {
            running: "bg-green-400",
            paused: "bg-yellow-400",
            archived: "bg-gray-400",
          }
          return (
            <NavLink
              key={scene.id}
              to={`/scenes/${scene.id}`}
              onClick={() => { if (collapsed) toggle() }}
              className={({ isActive }) => cn(
                "flex items-center gap-2.5 rounded-lg transition-all duration-200 w-full px-1.5 py-1 stagger-1",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50",
              )}
              title={hovered ? undefined : scene.name || scene.id}
              style={{ animationDelay: `${i * 0.04}s` }}
            >
              <SceneAvatar id={scene.id} size={activeSceneId === scene.id ? "md" : "sm"} />
              <div className="flex items-center gap-1.5 min-w-0">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusColors[scene.status] || "bg-gray-300"}`} />
                <span className={cn(
                  "text-xs text-sidebar-foreground truncate font-medium transition-opacity duration-200",
                  hovered ? "opacity-100 delay-75" : "opacity-0 delay-0",
                )}>{scene.name || scene.id}</span>
              </div>
            </NavLink>
          )
        })}
        <NavLink
          to="/scenes/new"
          className="flex items-center justify-center gap-2 w-full text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent rounded-lg py-1.5 mt-0.5 transition-all duration-200"
          title={t("component.new_scene")}
        >
          <Plus className="size-4 shrink-0" />
          <span className={cn(
            "text-xs transition-opacity duration-200",
            hovered ? "opacity-100 delay-75" : "opacity-0 delay-0",
          )}>{t("component.new_scene")}</span>
        </NavLink>
      </nav>

      <div className="w-6 border-t border-sidebar-border my-0.5" />

      <div className="flex flex-col items-center gap-1.5">
        <NavLink
          to="/scenes"
          className={({ isActive }) => cn(
            "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
            isActive
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent",
          )}
          title={t("nav.scenes")}
        >
          <Layers className="size-4" />
        </NavLink>
        <NavLink
          to="/agents"
          className={({ isActive }) => cn(
            "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
            isActive
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent",
          )}
          title={t("nav.agents")}
        >
          <Bot className="size-4" />
        </NavLink>
        <NavLink
          to="/knowledge"
          className={({ isActive }) => cn(
            "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200",
            isActive
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent",
          )}
          title={t("nav.knowledge")}
        >
          <Book className="size-4" />
        </NavLink>
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