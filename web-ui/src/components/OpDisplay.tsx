import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"
import Namecard from "./Namecard"
import VizEngine from "./viz/VizEngine"
import DefaultFunc from "./opdisplay/DefaultFunc"
import KbAdminFunc from "./opdisplay/KbAdminFunc"
import ScenesView from "./opdisplay/ScenesView"
import KnowledgeView from "./opdisplay/KnowledgeView"
import SettingsView from "./opdisplay/SettingsView"
import { Brain } from "lucide-react"
import type { QuickSendFn } from "./Layout"

interface OpDisplayProps {
  activeNav: string
  onQuickSend?: QuickSendFn
}

export default function OpDisplay({ activeNav, onQuickSend }: OpDisplayProps) {
  const { currentMode } = useMode()
  const t = useT()

  const renderFunc = () => {
    if (activeNav === "chat") {
      return currentMode === "kb-admin" ? <KbAdminFunc onQuickSend={onQuickSend} /> : <DefaultFunc onQuickSend={onQuickSend} />
    }
    switch (activeNav) {
      case "scenes": return <ScenesView />
      case "knowledge": return <KnowledgeView />
      case "settings": return <SettingsView />
      case "memory": return (
        <div className="flex flex-col items-center justify-center h-full animate-view-enter text-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
            <Brain className="size-6 text-muted-foreground/40" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground mb-1">Memory Timeline</h3>
            <p className="text-[11px] text-muted-foreground max-w-[240px]">
              Pinned facts and conversation memory will appear here. Use chat to build context.
            </p>
          </div>
        </div>
      )
      default: return <DefaultFunc onQuickSend={onQuickSend} />
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      <Namecard />
      <VizEngine />
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {renderFunc()}
      </div>
    </div>
  )
}
