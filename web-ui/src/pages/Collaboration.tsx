import { useState, useRef, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import dagre from "dagre"
import { api } from "@/api/client"
import { Skeleton } from "@/components/ui/skeleton"
import ErrorState from "@/components/ErrorState"
import { Button } from "@/components/ui/button"
import { useT } from "@/context/LanguageContext"

interface GraphNode {
  id: string
  label: string
}

interface ReplyInfo {
  from: string
  content: string
  timestamp: string
}

interface GraphEdge {
  id: string
  from: string
  to: string
  task_id: number
  type: string
  summary: string
  timestamp: string
  replies: ReplyInfo[]
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

const COLORS = [
  "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
]

export default function Collaboration() {
  const t = useT()
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["collaboration-graph"],
    queryFn: () => api.get<GraphData>("/collaboration/graph"),
    refetchInterval: selectedEdge ? false : 15000,
  })
  const colorMap = useMemo(() => {
    if (!data) return {} as Record<string, string>
    const m: Record<string, string> = {}
    data.nodes.forEach((n, i) => { m[n.id] = COLORS[i % COLORS.length] ?? "#3b82f6" })
    return m
  }, [data])

  const layout = useMemo(() => {
    if (!data || data.nodes.length === 0) return null
    const g = new dagre.graphlib.Graph()
    g.setGraph({ rankdir: "LR", nodesep: 80, ranksep: 120, marginx: 60, marginy: 60 })
    g.setDefaultEdgeLabel(() => ({}))
    data.nodes.forEach((n) => g.setNode(n.id, { width: 150, height: 60, label: n.label }))
    data.edges.forEach((e) => g.setEdge(e.from, e.to, { id: e.id }))
    dagre.layout(g)

    const nodePositions: Record<string, { x: number; y: number; w: number; h: number }> = {}
    g.nodes().forEach((id: string) => {
      const n = g.node(id)
      if (n) nodePositions[id] = { x: n.x - 75, y: n.y - 30, w: 150, h: 60 }
    })
    const edgePaths: Record<string, { points: { x: number; y: number }[] }> = {}
    g.edges().forEach((e: { v: string; w: string }) => {
      const edge = g.edge(e)
      edgePaths[`${e.v}->${e.w}`] = { points: edge.points || [] }
    })

    const allX = Object.values(nodePositions).flatMap(n => [n.x, n.x + n.w])
    const allY = Object.values(nodePositions).flatMap(n => [n.y, n.y + n.h])
    const minX = Math.min(...allX) - 40
    const minY = Math.min(...allY) - 40
    const maxX = Math.max(...allX) + 40
    const maxY = Math.max(...allY) + 40

    return { nodePositions, edgePaths, width: maxX - minX, height: maxY - minY, offsetX: -minX, offsetY: -minY }
  }, [data])

  if (isLoading) return <Skeleton className="h-96 w-full" />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />
  if (!data || data.nodes.length === 0) {
    return <div className="p-8 text-muted-foreground">{t("collab.no_data")}</div>
  }

  return (
    <div className="flex h-full">
      <div className="stagger-item flex-1 overflow-hidden p-4" style={{animationDelay: "0s"}}>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-semibold">{t("collab.title")}</h1>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {data.nodes.length} agents · {data.edges.length} interactions
            </span>
            <Button variant="outline" size="sm" onClick={() => { setPan({ x: 0, y: 0 }); setScale(1) }}>
              Reset
            </Button>
          </div>
        </div>
        {layout && (
          <svg
            className="border rounded bg-card w-full"
            style={{ height: Math.max(400, layout.height + 80), cursor: dragging ? "grabbing" : "grab" }}
            viewBox={`0 0 ${layout.width + 80} ${layout.height + 80}`}
            preserveAspectRatio="xMidYMid meet"
            onMouseDown={(e) => { setDragging(true); setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y }) }}
            onMouseMove={(e) => { if (dragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }) }}
            onMouseUp={() => setDragging(false)}
            onMouseLeave={() => setDragging(false)}
            onWheel={(e) => { e.preventDefault(); setScale(s => Math.max(0.3, Math.min(3, s * (e.deltaY > 0 ? 0.9 : 1.1)))) }}>
            <g transform={`translate(${layout.offsetX + 40}, ${layout.offsetY + 40})`}>
              <defs>
                <marker id="a-task" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0,0 L10,5 L0,10 Z" fill="#3b82f6" />
                </marker>
                <marker id="a-reply" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0,0 L10,5 L0,10 Z" fill="#22c55e" />
                </marker>
              </defs>
              {data.edges.map((edge) => {
                const ep = layout.edgePaths[`${edge.from}->${edge.to}`]
                if (!ep || !ep.points || ep.points.length < 2) return null
                const isTask = edge.type === "task"
                const d = ep.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ")
                return (
                  <g key={edge.id}>
                    <path d={d} fill="none" stroke={isTask ? "#3b82f6" : "#22c55e"}
                      strokeWidth={2} strokeDasharray={isTask ? "" : "6,3"}
                      markerEnd={`url(#a-${isTask ? "task" : "reply"})`}
                      className="cursor-pointer transition-opacity hover:opacity-100"
                      style={{ opacity: 0.7 }} onClick={() => setSelectedEdge(edge)} />
                    {(() => {
                      const mid = ep.points[Math.floor(ep.points.length / 2)]
                      if (!mid) return null
                      return (
                        <foreignObject x={mid.x - 60} y={mid.y - 20} width={120} height={18} className="pointer-events-none">
                          <div className="text-[9px] text-muted-foreground text-center leading-tight truncate bg-background/80 rounded px-1">
                            {edge.summary}
                          </div>
                        </foreignObject>
                      )
                    })()}
                  </g>
                )
              })}
              {data.nodes.map((node) => {
                const pos = layout.nodePositions[node.id]
                if (!pos) return null
                const color = colorMap[node.id] ?? "#3b82f6"
                return (
                  <g key={node.id}>
                    <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
                      rx={10} ry={10} fill="hsl(var(--card))" stroke={color} strokeWidth={2.5} />
                    <circle cx={pos.x + 22} cy={pos.y + 30} r={14} fill={color} />
                    <text x={pos.x + 22} y={pos.y + 34} textAnchor="middle" fontSize={11}
                      fill="#fff" fontWeight="bold">
                      {node.label.charAt(0)}
                    </text>
                    <text x={pos.x + 46} y={pos.y + 24} textAnchor="start" fontSize={12}
                      fill="hsl(var(--foreground))" fontWeight="bold">
                      {node.label}
                    </text>
                    <text x={pos.x + 46} y={pos.y + 42} textAnchor="start" fontSize={9}
                      fill="hsl(var(--muted-foreground))">
                      {node.id}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        )}
      </div>
      {selectedEdge && (
        <div className="stagger-item w-80 border-l bg-muted p-4 overflow-y-auto shrink-0" style={{animationDelay: "0.08s"}}>
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">{t("collab.task").replace("{id}", String(selectedEdge.task_id))}</h2>
            <Button variant="outline" size="sm" onClick={() => setSelectedEdge(null)}>&times;</Button>
          </div>
          <div className="space-y-3">
            <div className="bg-card rounded p-3 border-l-4 border-blue-500">
              <div className="text-xs text-muted-foreground mb-1">{selectedEdge.from} &rarr; {selectedEdge.to}</div>
              <div className="text-sm">{selectedEdge.summary}</div>
              <div className="text-xs text-muted-foreground mt-1">{selectedEdge.timestamp}</div>
            </div>
            {selectedEdge.replies.map((r, i) => (
              <div key={i} className="bg-card rounded p-3 border-l-4 border-green-500">
                <div className="text-xs text-muted-foreground mb-1">{r.from} &rarr; {selectedEdge.from}</div>
                <div className="text-sm">{r.content}</div>
                <div className="text-xs text-muted-foreground mt-1">{r.timestamp}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
