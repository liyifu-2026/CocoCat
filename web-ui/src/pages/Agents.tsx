import { useQuery } from "@tanstack/react-query"
import { Loader2, Bot, Cpu } from "lucide-react"

interface Agent {
  id: string
  name: string
  role: string
  status: string
  model?: string
  scene_id?: string | null
}

export default function AgentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetch("/api/agents").then(r => r.json()),
    refetchInterval: 5000,
  })

  const agents: Agent[] = (data as any)?.agents ?? []

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="p-6 space-y-4 h-full overflow-y-auto">
      <div className="flex items-center gap-3 mb-6">
        <Cpu className="size-5 text-muted-foreground" />
        <h1 className="text-lg font-bold">智能体</h1>
      </div>

      {agents.length === 0 && (
        <p className="text-sm text-muted-foreground">没有运行中的智能体</p>
      )}

      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {agents.map(agent => (
          <div
            key={agent.id}
            className="rounded-xl border border-border/60 bg-card p-5 space-y-3"
          >
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-primary" />
              <h3 className="font-medium">{agent.name}</h3>
              <span className={`ml-auto text-[10px] px-2 py-0.5 rounded-full font-medium ${
                agent.status === "running"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                  : "bg-muted text-muted-foreground"
              }`}>
                {agent.status === "running" ? "运行中" : agent.status}
              </span>
            </div>
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex justify-between">
                <span>ID</span>
                <span className="font-mono">{agent.id}</span>
              </div>
              <div className="flex justify-between">
                <span>角色</span>
                <span className={`font-mono ${
                  agent.role === "resident" ? "text-primary" : "text-muted-foreground"
                }`}>
                  {agent.role === "resident" ? "常驻" : agent.role === "worker" ? "执行者" : agent.role}
                </span>
              </div>
              {agent.model && (
                <div className="flex justify-between">
                  <span>模型</span>
                  <span className="font-mono">{agent.model}</span>
                </div>
              )}
              {agent.scene_id && (
                <div className="flex justify-between">
                  <span>绑定场景</span>
                  <span className="font-mono">{agent.scene_id}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
