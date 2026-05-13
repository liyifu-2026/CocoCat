import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

const SCENE_COLORS = [
  "bg-amber-600", "bg-emerald-600", "bg-rose-600", "bg-orange-600",
  "bg-teal-600", "bg-sky-600", "bg-violet-600", "bg-lime-600",
]

function hashColor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash)
  }
  return SCENE_COLORS[Math.abs(hash) % SCENE_COLORS.length]!
}

interface SceneAvatarProps {
  id: string
  color?: string
  size?: "sm" | "md"
}

export function SceneAvatar({ id, color, size = "sm" }: SceneAvatarProps) {
  const bgColor = color || hashColor(id)
  const initial = id.charAt(0).toUpperCase()
  const dim = size === "md" ? "w-9 h-9 text-sm" : "w-7 h-7 text-xs"

  return (
    <Avatar className={cn(dim, "rounded-lg shrink-0")}>
      <AvatarFallback className={cn(bgColor, "text-white font-display font-normal rounded-lg")}>
        {initial}
      </AvatarFallback>
    </Avatar>
  )
}