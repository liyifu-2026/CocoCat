import { useNavigate, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"
import {
  LayoutDashboard, MessageSquare, Users, Plus,
} from "lucide-react"

const navItems = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
]

interface MobileBottomNavProps {
  visible: boolean
}

export function MobileBottomNav({ visible }: MobileBottomNavProps) {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <nav
      className={cn(
        "fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/80 backdrop-blur-lg transition-transform duration-200 md:hidden",
        visible ? "translate-y-0" : "translate-y-full",
      )}
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="flex items-center justify-around h-14">
        {navItems.map(item => {
          const isActive = location.pathname.startsWith(item.to)
          return (
            <button
              key={item.to}
              onClick={() => navigate(item.to)}
              className={cn(
                "flex flex-col items-center gap-0.5 px-4 py-1 text-[10px] font-medium transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground",
              )}
            >
              <item.icon className="size-5" />
              <span>{t(item.labelKey)}</span>
            </button>
          )
        })}
        <button
          onClick={() => navigate("/scenes")}
          className="flex flex-col items-center gap-0.5 px-4 py-1 text-[10px] font-medium text-muted-foreground"
        >
          <div className="size-10 rounded-full bg-primary flex items-center justify-center -mt-3 shadow-sm">
            <Plus className="size-5 text-primary-foreground" />
          </div>
        </button>
      </div>
    </nav>
  )
}
