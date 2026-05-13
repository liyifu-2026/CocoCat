import { useState } from "react"
import { X, Clock, Heart, Bell } from "lucide-react"

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-[520px] rounded-2xl bg-card shadow-2xl border border-border/50 flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
        style={{ animation: "fadeSlideUp 0.2s ease-out both" }}
      >
        <div className="flex items-center justify-between border-b border-border px-5 h-13 shrink-0">
          <h2 className="text-sm font-display text-foreground flex items-center gap-2">
            <Clock className="size-4 text-tertiary" />
            定时任务
          </h2>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-6">
          {/* Cron Tasks */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Bell className="size-4 text-primary/70" />
              <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Cron 任务</h3>
            </div>
            <div className="space-y-2">
              {tasks.map(t => (
                <div key={t.id} className="rounded-xl border border-border/60 px-4 py-3 hover:shadow-sm transition-all duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">{t.schedule}</span>
                    <span className="text-xs text-muted-foreground/70 bg-muted/50 rounded-full px-2 py-0.5">{t.task}</span>
                  </div>
                  <p className="text-xs text-muted-foreground/60 mt-1.5 flex items-center gap-2">
                    <span>下次: {t.next}</span>
                    <button className="text-primary/70 hover:text-primary hover:underline underline-offset-2 transition-colors">编辑</button>
                  </p>
                </div>
              ))}
              <button className="text-xs text-muted-foreground/60 hover:text-foreground flex items-center gap-1.5 px-1 py-1.5 transition-colors">
                + 新建定时任务
              </button>
            </div>
          </div>

          {/* Heartbeat */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Heart className="size-4 text-rose-400" />
              <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">心跳</h3>
            </div>
            <div className="rounded-xl border border-border/60 px-4 py-3 hover:shadow-sm transition-all duration-200">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">主 AI</span>
                <span className="text-xs font-medium text-secondary">3 分钟前 ✓</span>
              </div>
              <p className="text-xs text-muted-foreground/60 mt-1.5">
                下次: 12 分钟后
              </p>
            </div>
            <button className="text-xs text-muted-foreground/60 hover:text-foreground flex items-center gap-1.5 px-1 py-2 transition-colors">
              编辑 heartbeat.md
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
