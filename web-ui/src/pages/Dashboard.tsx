import { useState, useEffect } from "react"
import { Activity, Cpu, Layers, Zap } from "lucide-react"

interface ModeInfo {
  id: string
  name: string
  description: string
}

export default function DashboardPage() {
  const [modes, setModes] = useState<ModeInfo[]>([])
  const [sessions, setSessions] = useState<{ id: string; title: string }[]>([])

  useEffect(() => {
    fetch("/api/modes").then(r => r.json()).then(setModes).catch(() => {})
    try {
      const raw = localStorage.getItem("cococat-sessions")
      if (raw) {
        const data = JSON.parse(raw)
        setSessions(data?.sessions?.slice(0, 5) || [])
      }
    } catch {}
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-display">Dashboard</h1>
        <p className="text-xs text-muted-foreground mt-1">系统状态一览</p>
      </div>
      <div className="flex-1 overflow-auto p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard icon={<Cpu className="size-5" />} label="运行模式" value={`${modes.length} 个`} detail={modes.map(m => m.name).join(" / ") || "加载中..."} />
          <StatusCard icon={<Layers className="size-5" />} label="活跃会话" value={`${sessions.length} 个`} detail="最近会话" />
          <StatusCard icon={<Zap className="size-5" />} label="系统状态" value="运行中" detail="ExecutorProvider 正常" />
        </div>

        <div className="rounded-xl border border-border bg-card/40 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-medium">可用模式</h2>
          </div>
          <div className="space-y-2">
            {modes.length === 0 && <p className="text-xs text-muted-foreground">加载模式列表...</p>}
            {modes.map(m => (
              <div key={m.id} className="flex items-center gap-3 rounded-lg bg-accent/20 px-4 py-2.5">
                <span className="text-sm font-medium">{m.name}</span>
                <span className="text-xs text-muted-foreground">{m.description}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusCard({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card/40 p-4 space-y-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-xl font-bold">{value}</div>
      {detail && <div className="text-xs text-muted-foreground">{detail}</div>}
    </div>
  )
}
