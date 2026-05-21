import { useMode } from "@/context/ModeContext"
import Namecard from "./Namecard"
import DefaultFunc from "./opdisplay/DefaultFunc"
import KbAdminFunc from "./opdisplay/KbAdminFunc"
import ScenesView from "./opdisplay/ScenesView"
import KnowledgeView from "./opdisplay/KnowledgeView"
import SettingsView from "./opdisplay/SettingsView"

interface OpDisplayProps {
  activeNav: string
}

export default function OpDisplay({ activeNav }: OpDisplayProps) {
  const { currentMode } = useMode()

  const renderFunc = () => {
    if (activeNav === "chat") {
      return currentMode === "kb-admin" ? <KbAdminFunc /> : <DefaultFunc />
    }
    switch (activeNav) {
      case "scenes": return <ScenesView />
      case "knowledge": return <KnowledgeView />
      case "settings": return <SettingsView />
      case "memory": return (
        <div className="p-4">
          <div className="bg-card border border-border rounded-xl p-3">
            <div className="text-[10px] font-semibold text-muted-foreground">🧠 Memory Timeline</div>
          </div>
        </div>
      )
      default: return <DefaultFunc />
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      <Namecard />
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {renderFunc()}
      </div>
    </div>
  )
}
