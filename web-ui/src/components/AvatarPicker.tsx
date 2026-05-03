import { AVATAR_ICONS, GENDER_COLORS, DEFAULT_COLORS } from "./avatars"

interface AvatarPickerProps {
  currentAvatar: string
  currentColor: string
  gender?: string
  onAvatarChange: (id: string) => void
  onColorChange: (color: string) => void
}

export function AvatarPicker({ currentAvatar, currentColor, gender, onAvatarChange, onColorChange }: AvatarPickerProps) {
  const genderPalette = gender ? GENDER_COLORS[gender] : null

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium mb-2 block">
          Avatar Icon
          {gender && <span className="text-muted-foreground ml-1">({gender === "male" ? "Suggest: tech icons" : "Suggest: nature icons"})</span>}
        </label>
        <div className="flex gap-1.5 flex-wrap">
          {AVATAR_ICONS.map(icon => {
            const IconComp = icon.component
            const isSelected = currentAvatar === icon.id
            return (
              <button key={icon.id} onClick={() => onAvatarChange(icon.id)}
                className={`h-9 w-9 flex items-center justify-center rounded-md transition-all ${
                  isSelected ? "bg-accent ring-1 ring-ring scale-110" : "hover:bg-accent/50"
                }`}
                title={icon.name}>
                <IconComp className={`w-5 h-5 ${isSelected ? "text-foreground" : "text-muted-foreground"}`} />
              </button>
            )
          })}
        </div>
      </div>
      <div>
        <label className="text-sm font-medium mb-2 block">
          Color
          {genderPalette && <span className="text-muted-foreground ml-1">(gender default: <span style={{ color: genderPalette.bg }}>●</span>)</span>}
        </label>
        <div className="flex gap-2 flex-wrap">
          {DEFAULT_COLORS.map(c => (
            <button key={c} onClick={() => onColorChange(c)}
              className={`h-7 w-7 rounded-full transition-all ${currentColor === c ? "ring-2 ring-offset-2 ring-foreground scale-110" : ""}`}
              style={{ backgroundColor: c }} />
          ))}
        </div>
      </div>
    </div>
  )
}
