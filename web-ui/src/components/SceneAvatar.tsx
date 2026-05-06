import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

const SCENE_COLORS = [
  "bg-blue-500", "bg-green-500", "bg-purple-500", "bg-orange-500",
  "bg-pink-500", "bg-teal-500", "bg-cyan-500", "bg-rose-500",
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
  avatar?: string
  color?: string
  size?: "sm" | "md"
}

export function SceneAvatar({ id, avatar, color, size = "sm" }: SceneAvatarProps) {
  const bgColor = color || hashColor(id)
  const initial = id.charAt(0).toUpperCase()
  const dim = size === "md" ? "w-9 h-9 text-sm" : "w-7 h-7 text-xs"

  return (
    <Avatar className={cn(dim, "rounded-md")}>
      <AvatarFallback className={cn(bgColor, "text-white font-medium rounded-md")}>
        {initial}
      </AvatarFallback>
    </Avatar>
  )
}
