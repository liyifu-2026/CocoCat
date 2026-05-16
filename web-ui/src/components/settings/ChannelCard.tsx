import { Circle } from "lucide-react"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { CHANNEL_ICONS } from "@/lib/channel-icons"

interface ChannelCardProps {
  typeInfo: ChannelTypeInfo
  mainInfo?: MainChannelInfo
  onClick: () => void
}

const CAPABILITY_LABELS: Record<string, string> = {
  text: "文字", image: "图片", voice: "语音", file: "文件",
  video: "视频", card: "卡片", streaming: "流式", threads: "多线程",
  reactions: "反馈", sticker: "表情", link: "链接", post: "富文本",
  event: "事件", location: "位置",
}

const STATUS_STYLES: Record<string, { border: string; bg: string; dot: string; text: string; label: string }> = {
  connected: {
    border: "border-green-400", bg: "bg-green-50/60",
    dot: "text-green-500 fill-green-500", text: "text-green-700",
    label: "已连接",
  },
  configured: {
    border: "border-amber-400", bg: "bg-amber-50/60",
    dot: "text-amber-500 fill-amber-500", text: "text-amber-700",
    label: "已配置",
  },
  unconfigured: {
    border: "border-border", bg: "",
    dot: "text-muted-foreground/30 fill-muted-foreground/30", text: "text-muted-foreground/50",
    label: "未配置",
  },
}

export function ChannelCard({ typeInfo, mainInfo, onClick }: ChannelCardProps) {
  const IconComp = CHANNEL_ICONS[typeInfo.channel_type]
  const status = mainInfo?.status ?? "unconfigured"
  const style = STATUS_STYLES[status]!

  // Collect capability tag labels
  const tags: string[] = []
  const caps = typeInfo.capabilities
  for (const key of ["text", "image", "voice", "file", "video"] as const) {
    if (caps.send.includes(key) || caps.receive.includes(key)) tags.push(CAPABILITY_LABELS[key]!)
  }
  if (caps.cards) tags.push(CAPABILITY_LABELS["card"]!)
  if (caps.streaming) tags.push(CAPABILITY_LABELS["streaming"]!)
  if (caps.threads) tags.push(CAPABILITY_LABELS["threads"]!)

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
        {style.label}
      </div>
    </button>
  )
}
