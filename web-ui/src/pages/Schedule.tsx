import { useState, useMemo } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { scheduleApi, type ScheduleTask, type CreateTaskRequest } from "@/api/schedule"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import {
  Plus, Trash2, Calendar, CheckCircle, Clock, AlertCircle,
  User, RefreshCw, ListTodo, TimerReset,
} from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-600 border-yellow-200",
  running: "bg-blue-500/10 text-blue-600 border-blue-200",
  completed: "bg-green-500/10 text-green-600 border-green-200",
  failed: "bg-red-500/10 text-red-600 border-red-200",
  cancelled: "bg-gray-500/10 text-gray-600 border-gray-200",
}

const RECURRING_INTERVALS = [
  { value: 30, label: "30 分钟" },
  { value: 60, label: "1 小时" },
  { value: 180, label: "3 小时" },
  { value: 360, label: "6 小时" },
  { value: 720, label: "12 小时" },
  { value: 1440, label: "24 小时" },
]

function formatTime(ts: string | undefined | null): string {
  if (!ts) return ""
  return ts.slice(0, 19).replace("T", " ")
}

function getRecurrenceLabel(task: ScheduleTask): string {
  if (!task.recurrence) return ""
  try {
    const r = JSON.parse(task.recurrence)
    const min = r.interval
    if (min <= 30) return "每30分钟"
    if (min <= 60) return "每小时"
    if (min <= 180) return "每3小时"
    if (min <= 360) return "每6小时"
    if (min <= 720) return "每12小时"
    return "每24小时"
  } catch {
    return ""
  }
}

function AgentQueueCard({
  agent,
  tasks,
}: {
  agent: { id: string; name: string; status?: string }
  tasks: ScheduleTask[]
}) {
  const running = tasks.find(t => t.status === "running")
  const queued = tasks.filter(t => t.status === "pending").slice(0, 3)
  const remaining = tasks.filter(t => t.status === "pending").length - queued.length
  const recurring = tasks.filter(t => t.task_type === "recurring_template")

  const statusDot = agent.status === "running" || agent.status === "online" ? "bg-green-500"
    : agent.status === "idle" ? "bg-yellow-400"
    : "bg-gray-400"

  return (
    <Card className="min-w-[220px] shrink-0">
      <CardHeader className="p-3 pb-0">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className={`size-2 rounded-full ${statusDot}`} />
          {agent.name}
          {running && <Badge variant="outline" className="text-xs ml-auto">工作中</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 space-y-1.5">
        {running && (
          <div className="text-xs bg-blue-50 dark:bg-blue-950 rounded p-1.5 flex items-start gap-1.5">
            <RefreshCw className="size-3 mt-0.5 shrink-0 text-blue-500 animate-spin" />
            <span className="line-clamp-2">{running.task}</span>
          </div>
        )}
        {!running && <div className="text-xs text-muted-foreground py-1">空闲中</div>}
        {queued.length > 0 && (
          <div className="text-xs space-y-0.5">
            <div className="text-muted-foreground">排队中:</div>
            {queued.map(t => (
              <div key={t.id} className="flex items-center gap-1 text-muted-foreground">
                <Clock className="size-2.5" />
                <span className="line-clamp-1">{t.task}</span>
              </div>
            ))}
            {remaining > 0 && <div className="text-muted-foreground">+{remaining} 个更多</div>}
          </div>
        )}
        {recurring.length > 0 && (
          <div className="text-xs space-y-0.5 pt-1 border-t">
            <div className="text-muted-foreground">周期性:</div>
            {recurring.map(t => (
              <div key={t.id} className="flex items-center gap-1 text-muted-foreground">
                <TimerReset className="size-2.5" />
                <span className="line-clamp-1">{getRecurrenceLabel(t)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TaskRow({ task, agentName, onDelete }: {
  task: ScheduleTask
  agentName: string
  onDelete: (id: number) => void
}) {
  const isRecurring = task.task_type === "recurring_template"
  const isCompleted = task.status === "completed" || task.status === "cancelled"

  return (
    <div className={`flex items-start gap-3 py-2.5 px-3 rounded-lg border transition-colors
      ${isCompleted ? "opacity-50" : ""}
      ${task.status === "running" ? "bg-blue-50/50 dark:bg-blue-950/20 border-blue-200" : "border-border"}
    `}>
      <div className="mt-0.5 shrink-0">
        {isRecurring
          ? <TimerReset className="size-4 text-purple-500" />
          : task.status === "running" ? <RefreshCw className="size-4 text-blue-500 animate-spin" />
          : task.status === "completed" ? <CheckCircle className="size-4 text-green-500" />
          : task.status === "failed" ? <AlertCircle className="size-4 text-red-500" />
          : task.status === "pending" ? <Clock className="size-4 text-yellow-500" />
          : <ListTodo className="size-4 text-muted-foreground" />
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{task.task}</div>
        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
          {!isRecurring && (
            <Badge variant="outline" className="text-xs">{agentName}</Badge>
          )}
          {isRecurring && (
            <Badge variant="outline" className="text-xs text-purple-600">
              ⏱ {getRecurrenceLabel(task)}
            </Badge>
          )}
          <span className={`px-1.5 py-0.5 rounded text-xs border ${STATUS_COLORS[task.status] ?? ""}`}>
            {task.status === "running" ? "进行中"
             : task.status === "pending" ? "排队中"
             : task.status === "completed" ? "已完成"
             : task.status === "failed" ? "失败"
             : task.status}
          </span>
          <span>{formatTime(task.created_at)}</span>
          {task.completed_at && <span>→ {formatTime(task.completed_at)}</span>}
        </div>
        {task.result && task.status === "completed" && (
          <div className="text-xs text-muted-foreground mt-1 truncate">
            结果: {task.result.slice(0, 200)}
          </div>
        )}
        {task.error && task.status === "failed" && (
          <div className="text-xs text-red-500 mt-1 truncate">
            错误: {task.error.slice(0, 200)}
          </div>
        )}
      </div>
      <Button size="xs" variant="ghost" className="shrink-0" onClick={() => onDelete(task.id)}>
        <Trash2 className="size-3" />
      </Button>
    </div>
  )
}

export default function Schedule() {
  const [createOpen, setCreateOpen] = useState(false)
  const [newTask, setNewTask] = useState("")
  const [newAssignee, setNewAssignee] = useState("")
  const [newType, setNewType] = useState<"one_time" | "recurring_template">("one_time")
  const [newInterval, setNewInterval] = useState(60)
  const [filter, setFilter] = useState<"all" | "pending" | "completed">("all")
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["schedule"],
    queryFn: () => scheduleApi.get(),
  })
  const { data: agentsData } = useQuery({
    queryKey: ["agents"],
    queryFn: () => agentsApi.list(),
  })

  const tasks: ScheduleTask[] = data?.tasks ?? []
  const agents = agentsData?.agents ?? []

  const tasksByAgent = useMemo(() => {
    const map: Record<string, ScheduleTask[]> = {}
    for (const t of tasks) {
      if (!map[t.assigned_to]) { map[t.assigned_to] = [] }
      map[t.assigned_to]!.push(t)
    }
    return map
  }, [tasks])

  const timelineTasks = useMemo(() => {
    let filtered = tasks.filter(t => t.task_type !== "recurring_instance")
    if (filter === "pending") filtered = filtered.filter(t => t.status === "pending" || t.status === "running")
    if (filter === "completed") filtered = filtered.filter(t => t.status === "completed" || t.status === "failed" || t.status === "cancelled")
    return filtered
  }, [tasks, filter])

  async function handleCreate() {
    if (!newTask.trim() || !newAssignee) return
    const req: CreateTaskRequest = {
      task: newTask.trim(),
      assigned_to: newAssignee,
    }
    if (newType === "recurring_template") {
      req.task_type = "recurring_template"
      req.recurrence = newInterval
    }
    await scheduleApi.create(req)
    toast.success(newType === "recurring_template" ? "周期性任务已创建" : "任务已创建")
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
    setCreateOpen(false)
    setNewTask("")
    setNewAssignee("")
    setNewType("one_time")
  }

  async function handleDelete(taskId: number) {
    await scheduleApi.delete(taskId)
    toast.success("任务已删除")
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ListTodo className="size-6" /> 任务中心
        </h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> 新建任务</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>新建任务</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">任务描述</label>
                <Textarea value={newTask} onChange={e => setNewTask(e.target.value)}
                  placeholder="描述任务内容..." className="min-h-[100px]" />
              </div>
              <div>
                <label className="text-sm font-medium">分配给</label>
                <Select value={newAssignee} onValueChange={setNewAssignee}>
                  <SelectTrigger><SelectValue placeholder="选择 Agent" /></SelectTrigger>
                  <SelectContent>
                    {agents.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">任务类型</label>
                <Tabs value={newType} onValueChange={v => setNewType(v as "one_time" | "recurring_template")}>
                  <TabsList className="grid grid-cols-2">
                    <TabsTrigger value="one_time">一次性</TabsTrigger>
                    <TabsTrigger value="recurring_template">周期性</TabsTrigger>
                  </TabsList>
                  <TabsContent value="recurring_template" className="pt-2">
                    <label className="text-sm font-medium">执行间隔</label>
                    <Select value={String(newInterval)} onValueChange={v => setNewInterval(Number(v))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {RECURRING_INTERVALS.map(i => (
                          <SelectItem key={i.value} value={String(i.value)}>{i.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TabsContent>
                </Tabs>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>取消</Button>
                <Button size="sm" onClick={handleCreate} disabled={!newTask.trim() || !newAssignee}>
                  创建
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      )}

      {isError && <ErrorState message={error?.message} onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          <div>
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <User className="size-4" /> Agent 任务队列
            </h2>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {agents.map(agent => (
                <AgentQueueCard
                  key={agent.id}
                  agent={agent}
                  tasks={tasksByAgent[agent.id] ?? []}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Calendar className="size-4" /> 任务时间线
              </h2>
              <Tabs value={filter} onValueChange={v => setFilter(v as "all" | "pending" | "completed")}>
                <TabsList>
                  <TabsTrigger value="all">全部</TabsTrigger>
                  <TabsTrigger value="pending">进行中</TabsTrigger>
                  <TabsTrigger value="completed">已完成</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {timelineTasks.length === 0 && (
              <div className="text-center py-20 text-muted-foreground">
                <ListTodo className="size-12 mx-auto mb-4 opacity-30" />
                <p>暂无任务</p>
              </div>
            )}

            <div className="space-y-1">
              {timelineTasks.map(task => {
                const agent = agents.find(a => a.id === task.assigned_to)
                return (
                  <TaskRow
                    key={task.id}
                    task={task}
                    agentName={agent?.name ?? task.assigned_to}
                    onDelete={handleDelete}
                  />
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
