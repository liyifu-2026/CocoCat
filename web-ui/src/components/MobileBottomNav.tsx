import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  MessageSquare, Folder, BookOpen, Brain, Settings,
} from "lucide-react"

const NAV_ITEMS = [
  { path: "/chat", icon: MessageSquare },
  { path: "/scenes", icon: Folder },
  { path: "/knowledge", icon: BookOpen },
  { path: "/memory", icon: Brain },
  { path: "/settings", icon: Settings },
] as const

export function MobileBottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/80 backdrop-blur-lg md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="flex items-center justify-around h-14">
        {NAV_ITEMS.map(({ path, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 text-[10px] font-medium transition-colors",
                isActive ? "text-primary" : "text-muted-foreground",
              )
            }
          >
            {({ isActive }) => (
              <Icon className="size-5" />
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
