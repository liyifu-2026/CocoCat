import { Circle } from "lucide-react"
import { useT } from "@/context/LanguageContext"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { CHANNEL_ICONS } from "@/lib/channel-icons"

interface ChannelCardProps {
  typeInfo: ChannelTypeInfo
  mainInfo?: MainChannelInfo
  onClick: () => void
}

export function ChannelCard({ typeInfo, mainInfo, onClick }: ChannelCardProps) {
  const t = useT()
  const IconComp = CHANNEL_ICONS[typeInfo.channel_type]
  const status = mainInfo?.status ?? "unconfigured"

  const STATUS_STYLES: Record<string, { border: string; bg: string; dot: string; text: string; labelKey: string }> = {
    connected: {
      border: "border-green-400", bg: "bg-emerald-500/10",
      dot: "text-green-500 fill-green-500", text: "text-emerald-400",
      labelKey: "channel.status_connected",
    },
    connecting: {
      border: "border-blue-400", bg: "bg-blue-500/10",
      dot: "text-blue-500 fill-blue-500", text: "text-blue-400",
      labelKey: "channel.status_connecting",
    },
    configured: {
      border: "border-amber-400", bg: "bg-amber-500/10",
      dot: "text-amber-500 fill-amber-500", text: "text-amber-400",
      labelKey: "channel.status_configured",
    },
    unconfigured: {
      border: "border-border", bg: "",
      dot: "text-muted-foreground/30 fill-muted-foreground/30", text: "text-muted-foreground/50",
      labelKey: "channel.status_unconfigured",
    },
  }
  const style = STATUS_STYLES[status]!

  const tags: string[] = []
  const caps = typeInfo.capabilities
  const capKeys = ["text", "image", "voice", "file", "video", "card", "streaming", "threads", "reactions", "sticker", "link", "post", "event", "location"] as const
  for (const key of capKeys) {
    if (key === "card" ? caps.cards : key === "streaming" ? caps.streaming : key === "threads" ? caps.threads : key === "reactions" ? caps.reactions : caps.send.includes(key) || caps.receive.includes(key)) {
      tags.push(t(`channel.cap_${key}`))
    }
  }

  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all duration-200 cursor-pointer
        ${style.border} ${style.bg}
        hover:shadow-md hover:scale-[1.02]`}
    >
      <div className="size-10 flex items-center justify-center text-foreground">
        {IconComp && <IconComp size={28} />}
      </div>
      <span className="text-sm font-semibold text-foreground">{typeInfo.display_name}</span>
      <span className="text-[10px] text-muted-foreground -mt-1">{typeInfo.english_name}</span>
      <div className="flex flex-wrap justify-center gap-1 mt-1">
        {tags.map(tag => (
          <span key={tag} className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-muted text-muted-foreground">
            {tag}
          </span>
        ))}
      </div>
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${style.bg ? style.bg : 'bg-muted'} ${style.text}`}>
        <Circle className={`size-1.5 ${style.dot}`} />
        {t(style.labelKey)}
      </div>
    </button>
  )
}
