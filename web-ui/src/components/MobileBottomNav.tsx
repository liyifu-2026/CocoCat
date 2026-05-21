import { cn } from "@/lib/utils"
import {
  MessageSquare, Folder, BookOpen, Brain, Settings,
} from "lucide-react"

interface MobileBottomNavProps {
  active: string
  onNavigate: (nav: string) => void
}

export function MobileBottomNav({ active, onNavigate }: MobileBottomNavProps) {
  const items = [
    { key: "chat", icon: MessageSquare },
    { key: "scenes", icon: Folder },
    { key: "knowledge", icon: BookOpen },
    { key: "memory", icon: Brain },
    { key: "settings", icon: Settings },
  ]

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/80 backdrop-blur-lg md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="flex items-center justify-around h-14">
        {items.map(item => (
          <button
            key={item.key}
            onClick={() => onNavigate(item.key)}
            className={cn(
              "flex flex-col items-center gap-0.5 px-3 py-1 text-[10px] font-medium transition-colors",
              active === item.key ? "text-primary" : "text-muted-foreground",
            )}
          >
            <item.icon className="size-5" />
          </button>
        ))}
      </div>
    </nav>
  )
}
