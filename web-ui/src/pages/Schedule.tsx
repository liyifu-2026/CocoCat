import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { scheduleApi } from "@/api/schedule"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Plus, Trash2, Calendar, CheckCircle, Clock } from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { Skeleton } from "@/components/ui/skeleton"
import { useT } from "@/context/LanguageContext"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-600 border-yellow-200",
  completed: "bg-green-500/10 text-green-600 border-green-200",
  failed: "bg-red-500/10 text-red-600 border-red-200",
}

export default function Schedule() {
  const [createOpen, setCreateOpen] = useState(false)
  const [newTask, setNewTask] = useState("")
  const [newAssignee, setNewAssignee] = useState("")
  const queryClient = useQueryClient()
  const t = useT()

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["schedule"], queryFn: () => scheduleApi.get() })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })

  const tasks = data?.tasks ?? []
  const agents = agentsData?.agents ?? []

  const pendingTasks = tasks.filter(t => t.status === "pending")
  const completedTasks = tasks.filter(t => t.status === "completed")
  const failedTasks = tasks.filter(t => t.status === "failed")

  async function createTask() {
    if (!newTask.trim() || !newAssignee) return
    await scheduleApi.create(newTask.trim(), newAssignee)
    toast.success(t("schedule.created_toast"))
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
    setCreateOpen(false)
    setNewTask("")
    setNewAssignee("")
  }

  async function markDone(taskId: number) {
    await scheduleApi.update(taskId, { status: "completed" })
    toast.success(t("schedule.completed_toast"))
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  async function deleteTask(taskId: number) {
    await scheduleApi.delete(taskId)
    toast.success(t("schedule.deleted_toast"))
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  function TaskCard({ t: task }: { t: typeof tasks[0] }) {
    const agent = agents.find(a => a.id === task.assigned_to)
    return (
      <div className="rounded-lg border border-border p-4 space-y-2">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium">{task.task}</p>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              <Badge variant="outline">{agent?.name ?? task.assigned_to}</Badge>
              <span>{task.created_at?.slice(0, 19).replace("T", " ")}</span>
              <span className={`px-1.5 py-0.5 rounded text-xs border ${STATUS_COLORS[task.status] ?? ""}`}>
                {task.status}
              </span>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            {task.status === "pending" && (
              <Button size="xs" variant="outline" onClick={() => markDone(task.id)}>
                <CheckCircle className="size-3" />
              </Button>
            )}
            <Button size="xs" variant="outline" onClick={() => deleteTask(task.id)}>
              <Trash2 className="size-3" />
            </Button>
          </div>
        </div>
        {task.result && (
          <p className="text-xs text-muted-foreground border-t border-border pt-1 mt-1">
            {`${t("schedule.result")} ${task.result.slice(0, 200)}`}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="stagger-item flex items-center justify-between" style={{animationDelay: "0s"}}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Calendar className="size-6" /> {t("schedule.title")}
        </h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> {t("schedule.new_task")}</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>{t("schedule.new_task_title")}</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">{t("schedule.task_desc")}</label>
                <Textarea value={newTask} onChange={e => setNewTask(e.target.value)}
                  placeholder={t("schedule.task_desc_placeholder")} className="min-h-[100px]" />
              </div>
              <div>
                <label className="text-sm font-medium">{t("schedule.assign_to")}</label>
                <Select value={newAssignee} onValueChange={setNewAssignee}>
                  <SelectTrigger><SelectValue placeholder={t("schedule.select_agent")} /></SelectTrigger>
                  <SelectContent>
                    {agents.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
                <Button size="sm" onClick={createTask} disabled={!newTask.trim() || !newAssignee}>{t("common.create")}</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading && (
        <div className="stagger-item space-y-3" style={{animationDelay: "0.08s"}}>
          {[1,2,3].map(i => (
            <div key={i} className="rounded-lg border border-border p-4 space-y-2">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {isError && <div className="stagger-item" style={{animationDelay: "0.08s"}}><ErrorState message={error?.message} onRetry={refetch} /></div>}

      {!isLoading && !isError && tasks.length === 0 && (
        <div className="stagger-item text-center py-20 text-muted-foreground" style={{animationDelay: "0.08s"}}>
          <Calendar className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("schedule.no_tasks")}</p>
        </div>
      )}

      {pendingTasks.length > 0 && (
        <div className="stagger-item" style={{animationDelay: "0.16s"}}>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Clock className="size-4" /> {t("schedule.pending").replace("{count}", String(pendingTasks.length))}
          </h2>
          <div className="space-y-2">
            {pendingTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}

      {completedTasks.length > 0 && (
        <div className="stagger-item" style={{animationDelay: "0.24s"}}>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <CheckCircle className="size-4 text-green-500" /> {t("schedule.completed").replace("{count}", String(completedTasks.length))}
          </h2>
          <div className="space-y-2 opacity-60">
            {completedTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}

      {failedTasks.length > 0 && (
        <div className="stagger-item" style={{animationDelay: "0.32s"}}>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-red-500">
            {t("schedule.failed").replace("{count}", String(failedTasks.length))}
          </h2>
          <div className="space-y-2">
            {failedTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}
    </div>
  )
}
