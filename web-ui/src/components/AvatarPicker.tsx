import { useState } from "react"

const COLORS = [
  "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
  "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#6366F1",
]

const EMOJIS = [
  "😀", "😎", "🤖", "👨‍💻", "👩‍💻", "🐱", "🐶", "🦊", "🐼", "🐨",
  "🌟", "🔥", "💡", "🎯", "⚡", "🌈", "🍀", "🎨", "🚀", "💎",
  "👑", "🦁", "🦄", "🐉", "🦅", "🌺", "🌸", "⭐", "☀️", "🌙",
]

interface AvatarPickerProps {
  currentAvatar: string
  currentColor: string
  onAvatarChange: (avatar: string) => void
  onColorChange: (color: string) => void
}

export function AvatarPicker({ currentAvatar, currentColor, onAvatarChange, onColorChange }: AvatarPickerProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium mb-2 block">Color</label>
        <div className="flex gap-2 flex-wrap">
          {COLORS.map(c => (
            <button key={c} onClick={() => onColorChange(c)}
              className={`h-8 w-8 rounded-full transition-all ${currentColor === c ? "ring-2 ring-offset-2 ring-foreground scale-110" : ""}`}
              style={{ backgroundColor: c }} />
          ))}
        </div>
      </div>
      <div>
        <label className="text-sm font-medium mb-2 block">Avatar Emoji</label>
        <div className="flex gap-1.5 flex-wrap">
          {EMOJIS.map(e => (
            <button key={e} onClick={() => onAvatarChange(e)}
              className={`h-8 w-8 flex items-center justify-center rounded-md text-base transition-all ${currentAvatar === e ? "bg-accent ring-1 ring-ring scale-110" : "hover:bg-accent/50"}`}>
              {e}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
