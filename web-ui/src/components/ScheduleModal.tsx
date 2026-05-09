import { useState } from "react"
import { X, Clock, Heart } from "lucide-react"

interface ScheduleModalProps {
  open: boolean
  onClose: () => void
}

export function ScheduleModal({ open, onClose }: ScheduleModalProps) {
  const [tasks] = useState([
    { id: "1", schedule: "每天 9:00", task: "检查 KB 摄入", next: "明天 09:00" },
    { id: "2", schedule: "每 2 小时", task: "客服质量检查", next: "11:30" },
  ])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-[500px] h-[450px] rounded-lg bg-background shadow-xl flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-bold"><Clock className="inline size-4 mr-1" /> 定时任务</h2>
          <button onClick={onClose} className="hover:bg-muted rounded p-1"><X className="size-4" /></button>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Cron 任务</h3>
            {tasks.map(t => (
              <div key={t.id} className="rounded border px-3 py-2 mb-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm">⏰ {t.schedule}</span>
                  <span className="text-xs text-muted-foreground">{t.task}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  下次: {t.next}
                  <button className="ml-2 hover:text-foreground">编辑</button>
                </p>
              </div>
            ))}
            <button className="text-xs text-muted-foreground hover:text-foreground mt-1">
              + 新建定时任务
            </button>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">
              <Heart className="inline size-3 mr-1" /> 心跳
            </h3>
            <div className="rounded border px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">💓 主 AI</span>
                <span className="text-xs text-green-600">3 分钟前 ✓</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                下次: 12 分钟后
              </p>
            </div>
            <button className="text-xs text-muted-foreground hover:text-foreground mt-2">
              编辑 heartbeat.md
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
