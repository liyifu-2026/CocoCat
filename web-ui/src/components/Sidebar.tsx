import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useSidebar } from "@/context/SidebarContext"
import { useAuth } from "@/context/AuthContext"
import {
    LayoutDashboard, Users, FolderKanban, Settings, BookOpen, Mail, BarChart3,
   UserPlus, MessageSquare, Calendar, GitBranch,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { PanelLeftClose, PanelLeft, LogOut } from "lucide-react"

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/agents", label: "Agents", icon: Users },
  { to: "/scenes", label: "Scenes", icon: FolderKanban },
  { to: "/hiring", label: "Hiring", icon: UserPlus },
  { to: "/mailbox", label: "Mailbox", icon: Mail },
  { to: "/usage", label: "Usage", icon: BarChart3 },
  { to: "/schedule", label: "Schedule", icon: Calendar },
  { to: "/collaboration", label: "协作图", icon: GitBranch },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/settings", label: "Settings", icon: Settings },
]

export function Sidebar() {
  const { collapsed, toggle } = useSidebar()
  const { logout } = useAuth()

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
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
      {!collapsed && (
        <div className="border-t border-sidebar-border p-2">
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            <span>退出登录</span>
          </button>
        </div>
      )}
      {collapsed && (
        <div className="border-t border-sidebar-border p-2">
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-md px-2 py-2 text-red-500 hover:bg-red-50 transition-colors"
            title="退出登录"
          >
            <LogOut className="size-4 shrink-0" />
          </button>
        </div>
      )}
    </aside>
  )
}
