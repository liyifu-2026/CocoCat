import { AVATAR_ICONS, GENDER_COLORS } from "./avatars"

interface AgentAvatarProps {
  avatarId?: string
  gender?: string
  color?: string
  status?: "idle" | "busy"
  name?: string
  size?: "sm" | "md" | "lg" | "xs"
}

const SIZES = { xs: "h-5 w-5 text-[9px]", sm: "h-8 w-8 text-xs", md: "h-10 w-10 text-sm", lg: "h-14 w-14 text-lg" }
const STATUS_DOT = { xs: "h-1.5 w-1.5 -right-0.5 -bottom-0.5", sm: "h-2.5 w-2.5 -right-0.5 -bottom-0.5", md: "h-3 w-3 -right-0.5 -bottom-0.5", lg: "h-3.5 w-3.5 -right-0.5 -bottom-0.5" }

export function AgentAvatar({ avatarId, gender, color, status, name, size = "sm" }: AgentAvatarProps) {
  const icon = AVATAR_ICONS.find(i => i.id === avatarId)
  const IconComp = icon?.component
  const genderPalette = gender ? GENDER_COLORS[gender] : null
  const bgColor = color || genderPalette?.bg || "#e5e7eb"

  return (
    <div className={`relative shrink-0 ${SIZES[size]}`}>
      <div
        className={`${SIZES[size]} rounded-full flex items-center justify-center overflow-hidden`}
        style={{ backgroundColor: bgColor, color: "#fff" }}
      >
        {IconComp ? (
          <IconComp className="w-3/5 h-3/5" />
        ) : name ? (
          <span className="font-medium">{name.charAt(0).toUpperCase()}</span>
        ) : null}
      </div>
      {status && (
        <span className={`absolute rounded-full ring-1 ring-background ${STATUS_DOT[size]} ${
          status === "busy" ? "bg-red-500" : "bg-green-500"
        }`} />
      )}
    </div>
  )
}
