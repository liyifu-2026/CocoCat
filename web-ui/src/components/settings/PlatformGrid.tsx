import { AlertCircle, RefreshCw } from "lucide-react"
import { useT } from "@/context/LanguageContext"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { ChannelCard } from "./ChannelCard"

interface PlatformGridProps {
  typeInfos: ChannelTypeInfo[]
  mainChannels: MainChannelInfo[]
  onCardClick: (typeInfo: ChannelTypeInfo, mainInfo?: MainChannelInfo) => void
  loading?: boolean
  error?: string
  onRetry?: () => void
}

export function PlatformGrid({ typeInfos, mainChannels, onCardClick, loading, error, onRetry }: PlatformGridProps) {
  const t = useT()

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl border-2 border-border h-48 animate-pulse bg-muted/50" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <AlertCircle className="size-8 text-red-400" />
        <p className="text-sm text-muted-foreground">{error}</p>
        {onRetry && (
          <button onClick={onRetry} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent transition-colors">
            <RefreshCw className="size-3" />
            {t("platform.retry")}
          </button>
        )}
      </div>
    )
  }

  if (typeInfos.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <p className="text-sm text-muted-foreground/60">{t("platform.empty")}</p>
      </div>
    )
  }

  const channelMap = new Map(mainChannels.map(m => [m.channel_type, m]))

  return (
    <div className="grid grid-cols-3 gap-3 stagger-1">
      {typeInfos.map(ti => (
        <ChannelCard
          key={ti.channel_type}
          typeInfo={ti}
          mainInfo={channelMap.get(ti.channel_type)}
          onClick={() => onCardClick(ti, channelMap.get(ti.channel_type))}
        />
      ))}
    </div>
  )
}
