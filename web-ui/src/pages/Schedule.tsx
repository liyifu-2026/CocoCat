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

  const { data, isLoading } = useQuery({ queryKey: ["schedule"], queryFn: () => scheduleApi.get() })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })

  const tasks = data?.tasks ?? []
  const agents = agentsData?.agents ?? []

  const pendingTasks = tasks.filter(t => t.status === "pending")
  const completedTasks = tasks.filter(t => t.status === "completed")
  const failedTasks = tasks.filter(t => t.status === "failed")

  async function createTask() {
    if (!newTask.trim() || !newAssignee) return
    await scheduleApi.create(newTask.trim(), newAssignee)
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
    setCreateOpen(false)
    setNewTask("")
    setNewAssignee("")
  }

  async function markDone(taskId: number) {
    await scheduleApi.update(taskId, { status: "completed" })
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  async function deleteTask(taskId: number) {
    await scheduleApi.delete(taskId)
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  function TaskCard({ t }: { t: typeof tasks[0] }) {
    const agent = agents.find(a => a.id === t.assigned_to)
    return (
      <div className="rounded-lg border border-border p-4 space-y-2">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium">{t.task}</p>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              <Badge variant="outline">{agent?.name ?? t.assigned_to}</Badge>
              <span>{t.created_at?.slice(0, 19).replace("T", " ")}</span>
              <span className={`px-1.5 py-0.5 rounded text-xs border ${STATUS_COLORS[t.status] ?? ""}`}>
                {t.status}
              </span>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            {t.status === "pending" && (
              <Button size="xs" variant="outline" onClick={() => markDone(t.id)}>
                <CheckCircle className="size-3" />
              </Button>
            )}
            <Button size="xs" variant="outline" onClick={() => deleteTask(t.id)}>
              <Trash2 className="size-3" />
            </Button>
          </div>
        </div>
        {t.result && (
          <p className="text-xs text-muted-foreground border-t border-border pt-1 mt-1">
            Result: {t.result.slice(0, 200)}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Calendar className="size-6" /> Schedule
        </h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> New Task</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>New Scheduled Task</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Task Description</label>
                <Textarea value={newTask} onChange={e => setNewTask(e.target.value)}
                  placeholder="Describe the task..." className="min-h-[100px]" />
              </div>
              <div>
                <label className="text-sm font-medium">Assign To</label>
                <Select value={newAssignee} onValueChange={setNewAssignee}>
                  <SelectTrigger><SelectValue placeholder="Select agent..." /></SelectTrigger>
                  <SelectContent>
                    {agents.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button>
                <Button size="sm" onClick={createTask} disabled={!newTask.trim() || !newAssignee}>Create</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading...</p>}

      {!isLoading && tasks.length === 0 && (
        <div className="text-center py-20 text-muted-foreground">
          <Calendar className="size-12 mx-auto mb-4 opacity-30" />
          <p>No scheduled tasks yet</p>
        </div>
      )}

      {pendingTasks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Clock className="size-4" /> Pending ({pendingTasks.length})
          </h2>
          <div className="space-y-2">
            {pendingTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}

      {completedTasks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <CheckCircle className="size-4 text-green-500" /> Completed ({completedTasks.length})
          </h2>
          <div className="space-y-2 opacity-60">
            {completedTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}

      {failedTasks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-red-500">
            Failed ({failedTasks.length})
          </h2>
          <div className="space-y-2">
            {failedTasks.map(t => <TaskCard key={t.id} t={t} />)}
          </div>
        </div>
      )}
    </div>
  )
}
