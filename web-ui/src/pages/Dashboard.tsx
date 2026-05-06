import { useState, useEffect, useRef, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { agentsApi } from "@/api/agents"
import { scenesApi } from "@/api/scenes"
import { hiringApi } from "@/api/hiring"
import { chatApi } from "@/api/chat"
import { scheduleApi } from "@/api/schedule"
import { api } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Users, FolderKanban, UserPlus, MessageSquare, BarChart3, ListChecks, Activity } from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { Skeleton } from "@/components/ui/skeleton"
import { useT } from "@/context/LanguageContext"

interface GraphNode {
  id: string
  label: string
}

interface GraphEdge {
  id: string
  from: string
  to: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

function useCountUp(target: number, duration = 1000): number {
  const [value, setValue] = useState(0)
  const valueRef = useRef(0)
  const prevTarget = useRef<number | undefined>(undefined)
  const rafRef = useRef(0)

  useEffect(() => {
    if (target === prevTarget.current) return
    prevTarget.current = target

    const startValue = valueRef.current
    if (target === startValue) {
      setValue(target)
      return
    }

    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const next = Math.round(startValue + (target - startValue) * eased)
      setValue(next)
      valueRef.current = next
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      }
    }

    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return value
}

const CARD_IDS = ["agents", "scenes", "hiring", "tasks", "usage"] as const

function loadSavedOrder(): string[] {
  try {
    const saved = localStorage.getItem("dashboard-card-order")
    if (!saved) return []
    const parsed = JSON.parse(saved)
    if (Array.isArray(parsed) && parsed.length === CARD_IDS.length) return parsed
    return []
  } catch {
    return []
  }
}

export default function Dashboard() {
  const t = useT()
  const navigate = useNavigate()
  const [displayConfs, setDisplayConfs] = useState<Record<string, { nickname?: string }>>({})
  const [selectedMessage, setSelectedMessage] = useState<{ from: string; content: string } | null>(null)

  const agents = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const scenes = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const hires = useQuery({ queryKey: ["hiring"], queryFn: () => hiringApi.listPending() })
  const chatGroups = useQuery({ queryKey: ["chat-groups"], queryFn: () => chatApi.listGroups() })
  const schedule = useQuery({ queryKey: ["schedule"], queryFn: () => scheduleApi.get() })
  const usage = useQuery({ queryKey: ["usage"], queryFn: () => agentsApi.usage(100) })
  const collab = useQuery({ queryKey: ["collab-graph"], queryFn: () => api.get<GraphData>("/collaboration/graph") })

  const defaultGroup = chatGroups.data?.groups?.find(g => g.is_default) ?? chatGroups.data?.groups?.[0]
  const chatMessages = useQuery({
    queryKey: ["chat-messages", defaultGroup?.id],
    queryFn: () => chatApi.getMessages(defaultGroup!.id, 10),
    enabled: !!defaultGroup,
  })

  const onlineAgents = agents.data?.agents?.filter(a => a.status === "running").length ?? 0
  const sceneCount = scenes.data?.scenes?.length ?? 0
  const pendingHires = hires.data?.pending?.length ?? 0
  const pendingTasks = schedule.data?.tasks?.filter(t => t.status === "pending").length ?? 0
  const totalTokens = usage.data?.usage?.reduce((sum, u) => sum + u.total_tokens, 0) ?? 0
  const recentMessages = chatMessages.data?.messages?.slice(-5).reverse() ?? []

  useEffect(() => {
    if (!agents.data?.agents) return
    agents.data.agents.forEach(async (a: any) => {
      try {
        const r = await agentsApi.display(a.id)
        if (r?.nickname) setDisplayConfs(p => ({ ...p, [a.id]: { nickname: r.nickname } }))
      } catch {}
    })
  }, [agents.data])

  const agentsValue = useCountUp(onlineAgents, 1000)
  const scenesValue = useCountUp(sceneCount, 1000)
  const hiresValue = useCountUp(pendingHires, 1000)
  const tasksValue = useCountUp(pendingTasks, 1000)
  const usageValue = useCountUp(totalTokens, 1000)

  const countUpMap: Record<string, number> = {
    agents: agentsValue,
    scenes: scenesValue,
    hiring: hiresValue,
    tasks: tasksValue,
    usage: usageValue,
  }

  const [cardOrder, setCardOrderState] = useState<string[]>(loadSavedOrder)

  const setCardOrder = useCallback((order: string[]) => {
    setCardOrderState(order)
    localStorage.setItem("dashboard-card-order", JSON.stringify(order))
  }, [])

  const draggedRef = useRef<string | null>(null)

  const allMetrics = [
    { id: "agents", label: t("dashboard.online_agents"), value: onlineAgents, icon: Users, loading: agents.isLoading, path: "/agents" },
    { id: "scenes", label: t("dashboard.active_scenes"), value: sceneCount, icon: FolderKanban, loading: scenes.isLoading, path: "/scenes" },
    { id: "hiring", label: t("dashboard.pending_hires"), value: pendingHires, icon: UserPlus, loading: hires.isLoading, path: "/hiring" },
    { id: "tasks", label: t("dashboard.pending_tasks"), value: pendingTasks, icon: ListChecks, loading: schedule.isLoading, path: "/schedule" },
    { id: "usage", label: t("dashboard.token_usage"), value: totalTokens, icon: BarChart3, loading: usage.isLoading, path: "/usage" },
  ]

  const orderedMetrics: typeof allMetrics = (() => {
    if (cardOrder.length !== CARD_IDS.length)
      return allMetrics
    const map = new Map(allMetrics.map(m => [m.id, m]))
    const ordered = cardOrder.map(id => map.get(id)).filter(Boolean) as typeof allMetrics
    for (const m of allMetrics) {
      if (!ordered.some(o => o.id === m.id)) ordered.push(m)
    }
    return ordered
  })()

  const isAnyError = agents.isError || scenes.isError || hires.isError || chatMessages.isError

  const collabNodes = collab.data?.nodes ?? []
  const collabEdges = collab.data?.edges ?? []

  return (
    <div className="p-6 space-y-6" onDragOver={e => e.preventDefault()}>
      <h1 className="text-2xl font-bold">{t("dashboard.title")}</h1>

      {isAnyError && (
        <ErrorState
          message={agents.error?.message ?? scenes.error?.message ?? hires.error?.message ?? chatMessages.error?.message}
          onRetry={() => { agents.refetch(); scenes.refetch(); hires.refetch(); chatMessages.refetch() }}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5" onDragOver={e => e.preventDefault()}>
        {orderedMetrics.map((m, idx) => (
          <Card
            key={m.id}
            data-card-id={m.id}
            draggable
            onDragStart={() => { draggedRef.current = m.id }}
            onDragOver={e => e.preventDefault()}
            onDrop={() => {
              const fromId = draggedRef.current
              if (!fromId || fromId === m.id) return
              const ids = orderedMetrics.map(x => x.id)
              const fromIdx = ids.indexOf(fromId)
              const toIdx = ids.indexOf(m.id)
              ids.splice(fromIdx, 1)
              ids.splice(toIdx, 0, fromId)
              setCardOrder(ids)
            }}
            onClick={() => navigate(m.path)}
            className="cursor-pointer hover:shadow-lg transition-shadow draggable-card"
            style={{
              opacity: 0,
              animation: `fadeInUp 0.4s ease-out forwards`,
              animationDelay: `${idx * 0.08}s`,
            }}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{m.label}</CardTitle>
              <m.icon className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {m.loading ? <Skeleton className="h-8 w-16" /> : countUpMap[m.id]}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg flex items-center justify-between">
              <span>{t("dashboard.agents_card")}</span>
              <button onClick={() => navigate("/agents")} className="text-xs text-muted-foreground hover:text-foreground cursor-pointer">
                {t("common.view_all")}
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {agents.data?.agents?.map(a => (
              <div key={a.id} className="flex items-center justify-between group relative">
                <span
                  className="font-medium cursor-pointer hover:text-primary"
                  onClick={() => navigate(`/agents/${a.id}`)}
                >
                  {displayConfs[a.id]?.nickname || a.name}
                  <span className="absolute bottom-full left-0 mb-1 hidden group-hover:block bg-popover text-popover-foreground text-xs rounded px-2 py-1 shadow-lg whitespace-nowrap z-10 border border-border">
                    {t("common.status")}: {a.status} | {t("common.scene")}: {a.scene || "—"}
                  </span>
                </span>
                <Badge variant={a.status === "running" ? "default" : "secondary"}>
                  {a.status === "running" ? t("common.online") : a.status === "error" ? t("common.error_status") : t("common.offline")}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">{t("dashboard.recent_chat")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 max-h-64 overflow-auto">
            {recentMessages.length === 0 && (
              <div className="text-sm text-muted-foreground">{t("common.no_data")}</div>
            )}
            {recentMessages.map((m, i) => (
              <div
                key={i}
                className="text-sm border-b border-border pb-1 cursor-pointer hover:bg-muted/50 rounded px-1"
                onClick={() => setSelectedMessage({ from: m.from, content: m.content })}
              >
                <span className="font-medium">[{m.from}]</span> {m.content.substring(0, 120)}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card
          className="lg:col-span-3 cursor-pointer hover:shadow-lg transition-shadow"
          onClick={() => navigate("/collaboration")}
        >
          <CardHeader>
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Activity className="size-4" /> {t("dashboard.collaboration")}
              </span>
              <span className="text-xs text-muted-foreground">
                {collabNodes.length} agents · {collabEdges.length} interactions
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {collab.isLoading ? (
              <Skeleton className="h-[200px] w-full" />
            ) : collab.isError ? (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                {t("common.error")}
              </div>
            ) : collabNodes.length === 0 ? (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                {t("common.no_data")}
              </div>
            ) : (
              <div className="flex items-center gap-6">
                <div className="flex-1 min-w-0">
                  <svg viewBox="0 0 500 220" className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
                    {(() => {
                      const cx = 250, cy = 110, rx = 200, ry = 85
                      const total = collabNodes.length
                      const colors = ["#3b82f6","#22c55e","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
                      const positions = collabNodes.map((_, i) => {
                        const angle = (2 * Math.PI * i) / total - Math.PI / 2
                        return { x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle) }
                      })
                      return (
                        <>
                          {collabEdges.map(edge => {
                            const fromIdx = collabNodes.findIndex(n => n.id === edge.from)
                            const toIdx = collabNodes.findIndex(n => n.id === edge.to)
                            if (fromIdx === -1 || toIdx === -1) return null
                            const fp = positions[fromIdx]!
                            const tp = positions[toIdx]!
                            return (
                              <line key={edge.id} x1={fp.x} y1={fp.y} x2={tp.x} y2={tp.y}
                                stroke="hsl(var(--muted-foreground))" strokeWidth="1.5" opacity="0.4" />
                            )
                          })}
                          {collabNodes.map((node, i) => {
                            const pos = positions[i]!
                            const color = colors[i % colors.length]
                            return (
                              <g key={node.id}>
                                <circle cx={pos.x} cy={pos.y} r={18} fill={color} />
                                <text x={pos.x} y={pos.y + 5} textAnchor="middle" fontSize={12}
                                  fill="#fff" fontWeight="bold">
                                  {node.label.charAt(0).toUpperCase()}
                                </text>
                                <text x={pos.x} y={pos.y + 30} textAnchor="middle" fontSize={9}
                                  fill="hsl(var(--muted-foreground))">
                                  {node.label.length > 8 ? node.label.substring(0, 8) + "\u2026" : node.label}
                                </text>
                              </g>
                            )
                          })}
                        </>
                      )
                    })()}
                  </svg>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={!!selectedMessage} onOpenChange={open => { if (!open) setSelectedMessage(null) }}>
        {selectedMessage && (
          <DialogContent>
            <DialogHeader>
              <DialogTitle>[{selectedMessage.from}]</DialogTitle>
            </DialogHeader>
            <div className="text-sm whitespace-pre-wrap">{selectedMessage.content}</div>
          </DialogContent>
        )}
      </Dialog>

      <div className="fixed bottom-4 right-4 flex items-center gap-2 z-50">
        <span className="relative flex size-3">
          <span className="absolute inline-flex size-full rounded-full bg-green-400 opacity-75 animate-ping" />
          <span className="relative inline-flex size-3 rounded-full bg-green-500" />
        </span>
        <span className="text-xs text-muted-foreground">{t("dashboard.live")}</span>
      </div>

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .draggable-card { cursor: grab; }
        .draggable-card:active { cursor: grabbing; }
      `}</style>
    </div>
  )
}
