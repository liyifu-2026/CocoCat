import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useSidebar } from "@/context/SidebarContext"
import { useAuth } from "@/context/AuthContext"
import { useTranslation } from "@/context/LanguageContext"
import {
    LayoutDashboard, Users, FolderKanban, Settings, BookOpen, Mail, BarChart3,
   UserPlus, MessageSquare, Calendar, GitBranch,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { PanelLeftClose, PanelLeft, LogOut, Languages } from "lucide-react"

const navItems = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
  { to: "/scenes", labelKey: "nav.scenes", icon: FolderKanban },
  { to: "/hiring", labelKey: "nav.hiring", icon: UserPlus },
  { to: "/mailbox", labelKey: "nav.mailbox", icon: Mail },
  { to: "/usage", labelKey: "nav.usage", icon: BarChart3 },
  { to: "/schedule", labelKey: "nav.schedule", icon: Calendar },
  { to: "/collaboration", labelKey: "nav.collaboration", icon: GitBranch },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
]

export function Sidebar() {
  const { collapsed, toggle } = useSidebar()
  const { logout } = useAuth()
  const { t, lang, setLang } = useTranslation()

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        {!collapsed && (
          <span className="font-semibold text-sidebar-foreground">CocoCat</span>
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={toggle}
          className="text-sidebar-foreground"
        >
          {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
        </Button>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )
            }
          >
            <item.icon className="size-4 shrink-0" />
            {!collapsed && <span>{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-sidebar-border p-2 space-y-1">
        {!collapsed && (
          <button
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <Languages className="size-4 shrink-0" />
            <span>{lang === "zh" ? "English" : "中文"}</span>
          </button>
        )}
        {collapsed && (
          <button
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}
            className="flex w-full items-center justify-center rounded-md px-2 py-2 text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            title={lang === "zh" ? "English" : "中文"}
          >
            <Languages className="size-4 shrink-0" />
          </button>
        )}
        {!collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            <span>{t("nav.logout")}</span>
          </button>
        )}
        {collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-md px-2 py-2 text-red-500 hover:bg-red-50 transition-colors"
            title={t("nav.logout")}
          >
            <LogOut className="size-4 shrink-0" />
          </button>
        )}
      </div>
    </aside>
  )
}
