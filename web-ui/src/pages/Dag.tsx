import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  GitBranch, Loader2, ChevronRight, ChevronDown,
  Circle, CheckCircle2, Clock, AlertCircle,
  ListTree, Network,
} from "lucide-react"
import DagGraph from "../components/DagGraph"

interface Task {
  id: string
  status: string
  result?: string
  error?: string
}

interface Stage {
  id: string
  name?: string
  status?: string
  tasks: Task[]
  parallel?: boolean
  depends_on?: string[]
}

interface DagRun {
  run_id: string
  created_by?: string
  status: string
  stages: Stage[]
}

const statusIcon = (status: string) => {
  switch (status) {
    case "done": return <CheckCircle2 className="size-3.5 text-green-500" />
    case "running": return <Loader2 className="size-3.5 text-blue-500 animate-spin" />
    case "pending": return <Clock className="size-3.5 text-muted-foreground/50" />
    case "failed": return <AlertCircle className="size-3.5 text-red-500" />
    default: return <Circle className="size-3.5 text-muted-foreground/30" />
  }
}

const statusColor = (status: string) => {
  switch (status) {
    case "done": return "text-green-600"
    case "running": return "text-blue-600"
    case "pending": return "text-muted-foreground/60"
    case "failed": return "text-red-600"
    default: return "text-muted-foreground/50"
  }
}

export default function DagPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["dag"],
    queryFn: () => fetch("/api/dag").then(r => r.json()),
    refetchInterval: 3000, // Poll every 3s for real-time updates
  })

  const runs: DagRun[] = (data as { runs?: DagRun[] })?.runs ?? []
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set())
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<"tree" | "graph">("tree")

  const toggleRun = (id: string) => {
    setExpandedRuns(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleStage = (stageKey: string) => {
    setExpandedStages(prev => {
      const next = new Set(prev)
      next.has(stageKey) ? next.delete(stageKey) : next.add(stageKey)
      return next
    })
  }

  if (isLoading && runs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <GitBranch className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-bold">DAG 任务图</h1>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-border/60 bg-muted/30 p-0.5">
            <button
              onClick={() => setViewMode("tree")}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                viewMode === "tree"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <ListTree className="size-3.5 inline mr-1" />
              列表
            </button>
            <button
              onClick={() => setViewMode("graph")}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                viewMode === "graph"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Network className="size-3.5 inline mr-1" />
              图形
            </button>
          </div>
          <button
            onClick={() => refetch()}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors ml-2"
          >
            刷新
          </button>
        </div>
      </div>

      {runs.length === 0 && (
        <div className="rounded-xl border border-dashed border-border p-12 text-center">
          <GitBranch className="size-8 text-muted-foreground/20 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">暂无运行中的 DAG 任务</p>
          <p className="text-xs text-muted-foreground/50 mt-1">
            Main AI 收到复杂任务时将自动生成 DAG
          </p>
        </div>
      )}

      {viewMode === "graph" && runs.length > 0 && (
        <div className="space-y-6">
          {runs.map(run => (
            <div key={run.run_id}>
              <div className="flex items-center gap-2 mb-3 px-1">
                <span className="text-sm font-mono text-foreground/80">{run.run_id}</span>
                <span className={`text-xs font-medium ${statusColor(run.status)}`}>
                  {run.status}
                </span>
              </div>
              <DagGraph run={run} />
            </div>
          ))}
        </div>
      )}

      {viewMode === "tree" && (
      <div className="space-y-3">
        {runs.map(run => (
          <div
            key={run.run_id}
            className="rounded-xl border border-border/60 bg-card overflow-hidden hover:shadow-sm transition-shadow duration-200"
          >
            {/* Run header */}
            <button
              onClick={() => toggleRun(run.run_id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
            >
              {expandedRuns.has(run.run_id)
                ? <ChevronDown className="size-4 text-muted-foreground shrink-0" />
                : <ChevronRight className="size-4 text-muted-foreground shrink-0" />
              }
              <span className="text-sm font-mono text-foreground/80">{run.run_id}</span>
              <span className={`text-xs font-medium ${statusColor(run.status)} ml-auto`}>
                {run.status}
              </span>
              <span className="text-xs text-muted-foreground/50">
                {run.stages?.length || 0} stages
              </span>
            </button>

            {/* Expanded stages */}
            {expandedRuns.has(run.run_id) && (
              <div className="border-t border-border/30 px-4 py-2 space-y-1.5 bg-muted/10">
                {run.stages?.map((stage, si) => {
                  const stageKey = `${run.run_id}-${stage.id}`
                  const doneCount = stage.tasks?.filter(t => t.status === "done").length || 0
                  const totalCount = stage.tasks?.length || 0

                  return (
                    <div key={stage.id} className="rounded-lg overflow-hidden">
                      {/* Stage header */}
                      <button
                        onClick={() => toggleStage(stageKey)}
                        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/40 rounded-lg transition-colors"
                      >
                        {expandedStages.has(stageKey)
                          ? <ChevronDown className="size-3.5 text-muted-foreground shrink-0" />
                          : <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
                        }
                        {stage.parallel && (
                          <span className="text-[10px] text-blue-500/70 font-medium px-1.5 py-0.5 rounded bg-blue-500/10">∥</span>
                        )}
                        <span className="text-sm font-medium">{stage.name || stage.id}</span>
                        <span className="text-xs text-muted-foreground/70 ml-auto">
                          {doneCount}/{totalCount} done
                        </span>
                      </button>

                      {/* Task list */}
                      {expandedStages.has(stageKey) && (
                        <div className="pl-8 pr-2 py-1 space-y-0.5">
                          {stage.tasks?.map(task => (
                            <div
                              key={task.id}
                              className="flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-muted/20 transition-colors"
                            >
                              {statusIcon(task.status)}
                              <span className="text-xs font-mono text-foreground/70">{task.id}</span>
                              <span className={`text-[10px] font-medium ${statusColor(task.status)} ml-auto`}>
                                {task.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>
      )}
    </div>
  )
}
