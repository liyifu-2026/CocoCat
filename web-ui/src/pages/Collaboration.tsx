import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import dagre from "dagre"
import { api } from "@/api/client"
import { agentsApi } from "@/api/agents"
import { Skeleton } from "@/components/ui/skeleton"
import ErrorState from "@/components/ErrorState"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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

type ViewMode = "graph" | "threads"

export default function Collaboration() {
  const t = useT()
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("graph")

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["collaboration-graph"],
    queryFn: () => api.get<GraphData>("/collaboration/graph"),
    refetchInterval: 15000,
  })
  const { data: displayData } = useQuery({
    queryKey: ["agent-displays"],
    queryFn: () => agentsApi.listDisplays(),
  })

  const colorMap = useMemo(() => {
    const map: Record<string, string> = {}
    data?.nodes?.forEach((n, i) => { map[n.id] = COLORS[i % COLORS.length]! })
    return map
  }, [data])

  const displayNames = useMemo(() => {
    const map: Record<string, string> = {}
    data?.nodes?.forEach(n => {
      map[n.id] = displayData?.[n.id]?.nickname || n.label
    })
    return map
  }, [data, displayData])

  // Dagre layout computation
  const layout = useMemo(() => {
    if (!data || !data.nodes.length) return null
    const g = new dagre.graphlib.Graph()
    g.setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: "TB", nodesep: 50, ranksep: 60, marginx: 40, marginy: 40 })

    data.nodes.forEach(n => {
      g.setNode(n.id, { width: 120, height: 48 })
    })
    data.edges.forEach(e => {
      g.setEdge(e.from, e.to, {})
    })

    dagre.layout(g)

    const nodes: { id: string; x: number; y: number; label: string; color: string; displayName: string }[] = []
    g.nodes().forEach(nid => {
      const n = g.node(nid)
      nodes.push({
        id: nid,
        x: n.x,
        y: n.y,
        label: data.nodes.find(dn => dn.id === nid)?.label ?? nid,
        color: colorMap[nid] ?? "#3b82f6",
        displayName: displayNames[nid] ?? nid,
      })
    })

    const edges = data.edges.map(e => ({
      ...e,
      fromX: g.node(e.from)?.x ?? 0,
      fromY: g.node(e.from)?.y ?? 0,
      toX: g.node(e.to)?.x ?? 0,
      toY: g.node(e.to)?.y ?? 0,
    }))

    return { nodes, edges, width: g.graph().width ?? 600, height: g.graph().height ?? 400 }
  }, [data, colorMap, displayNames])

  const renderGraph = useCallback(() => {
    if (!layout || !svgRef.current) return
    const svg = svgRef.current
    const w = layout.width + 60
    const h = layout.height + 60

    while (svg.firstChild) svg.removeChild(svg.firstChild)
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`)
    const svgns = "http://www.w3.org/2000/svg"

    // Arrow marker
    const defs = document.createElementNS(svgns, "defs")
    defs.innerHTML = `
      <marker id="arrow-task" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="#3b82f6"/>
      </marker>
      <marker id="arrow-reply" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="#22c55e"/>
      </marker>
      <marker id="arrow-hover" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="#8b5cf6"/>
      </marker>
    `
    svg.appendChild(defs)

    // Edges
    const edgeGroup = document.createElementNS(svgns, "g")
    layout.edges.forEach(edge => {
      const line = document.createElementNS(svgns, "line")
      line.setAttribute("x1", String(edge.fromX))
      line.setAttribute("y1", String(edge.fromY + 24))
      line.setAttribute("x2", String(edge.toX))
      line.setAttribute("y2", String(edge.toY - 24))
      line.setAttribute("stroke", edge.type === "task" ? "#3b82f6" : "#22c55e")
      line.setAttribute("stroke-width", "2")
      line.setAttribute("stroke-dasharray", edge.type === "task" ? "" : "6,3")
      line.setAttribute("marker-end", `url(#arrow-${edge.type === "task" ? "task" : "reply"})`)
      line.setAttribute("opacity", "0.5")
      line.style.cursor = "pointer"
      line.onclick = () => {
        const found = data?.edges.find(e => e.id === edge.id)
        if (found) setSelectedEdge(found)
      }
      edgeGroup.appendChild(line)
    })
    svg.appendChild(edgeGroup)

    // Nodes
    const nodeGroup = document.createElementNS(svgns, "g")
    layout.nodes.forEach(node => {
      // Node rect
      const rect = document.createElementNS(svgns, "rect")
      rect.setAttribute("x", String(node.x - 56))
      rect.setAttribute("y", String(node.y - 22))
      rect.setAttribute("width", "112")
      rect.setAttribute("height", "44")
      rect.setAttribute("rx", "8")
      rect.setAttribute("fill", node.color)
      rect.setAttribute("opacity", "0.15")
      rect.setAttribute("stroke", node.color)
      rect.setAttribute("stroke-width", "1.5")
      rect.style.cursor = "pointer"

      // Node initial circle
      const circle = document.createElementNS(svgns, "circle")
      circle.setAttribute("cx", String(node.x - 32))
      circle.setAttribute("cy", String(node.y))
      circle.setAttribute("r", "14")
      circle.setAttribute("fill", node.color)

      const initial = document.createElementNS(svgns, "text")
      initial.setAttribute("x", String(node.x - 32))
      initial.setAttribute("y", String(node.y + 5))
      initial.setAttribute("text-anchor", "middle")
      initial.setAttribute("font-size", "12")
      initial.setAttribute("font-weight", "bold")
      initial.setAttribute("fill", "#fff")
      initial.style.pointerEvents = "none"
      initial.textContent = node.displayName.charAt(0)

      const label = document.createElementNS(svgns, "text")
      label.setAttribute("x", String(node.x))
      label.setAttribute("y", String(node.y + 4))
      label.setAttribute("text-anchor", "middle")
      label.setAttribute("font-size", "11")
      label.setAttribute("fill", "currentColor")
      label.setAttribute("font-weight", "500")
      label.textContent = node.displayName

      const hoverRect = document.createElementNS(svgns, "rect")
      hoverRect.setAttribute("x", String(node.x - 56))
      hoverRect.setAttribute("y", String(node.y - 22))
      hoverRect.setAttribute("width", "112")
      hoverRect.setAttribute("height", "44")
      hoverRect.setAttribute("fill", "transparent")
      hoverRect.style.cursor = "pointer"

      const connected = new Set<string>()
      layout.edges.forEach(e => {
        if (e.from === node.id || e.to === node.id) {
          connected.add(e.from)
          connected.add(e.to)
        }
      })

      hoverRect.onmouseenter = () => setHoveredNode(node.id)
      hoverRect.onmouseleave = () => setHoveredNode(null)

      nodeGroup.appendChild(rect)
      nodeGroup.appendChild(circle)
      nodeGroup.appendChild(initial)
      nodeGroup.appendChild(label)
      nodeGroup.appendChild(hoverRect)
    })
    svg.appendChild(nodeGroup)
  }, [layout, data])

  useEffect(() => { if (viewMode === "graph") renderGraph() }, [renderGraph, viewMode])

  // Group edges by task for threads view
  const threadGroups = useMemo(() => {
    if (!data?.edges) return []
    const groups = new Map<number, GraphEdge[]>()
    data.edges.forEach(e => {
      const list = groups.get(e.task_id) || []
      list.push(e)
      groups.set(e.task_id, list)
    })
    return [...groups.entries()].sort(([a], [b]) => b - a)
  }, [data])

  if (isLoading) return <Skeleton className="h-96 w-full" />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />
  if (!data || data.nodes.length === 0) {
    return <div className="p-8 text-muted-foreground">{t("collab.no_data")}</div>
  }

  return (
    <div className="flex h-full">
      {/* Main area */}
      <div className="stagger-item flex-1 overflow-hidden flex flex-col" style={{animationDelay: "0s"}}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 pb-0">
          <h1 className="text-lg font-semibold">{t("collab.title")}</h1>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {data.nodes.length} agents · {data.edges.length} interactions
            </span>
            <div className="flex gap-1 bg-muted rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("graph")}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === "graph" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                }`}
              >
                Graph
              </button>
              <button
                onClick={() => setViewMode("threads")}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === "threads" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                }`}
              >
                Threads
              </button>
            </div>
          </div>
        </div>

        {/* Graph View */}
        {viewMode === "graph" && (
          <div className="flex-1 overflow-auto p-4">
            <div className="border rounded-lg bg-card overflow-auto" style={{ maxHeight: "70vh" }}>
              <svg ref={svgRef} className="w-full" style={{ minHeight: 500 }} />
            </div>
          </div>
        )}

        {/* Threads View */}
        {viewMode === "threads" && (
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {threadGroups.map(([taskId, edges]) => (
              <Card key={taskId} className="cursor-pointer hover:border-primary/30 transition-colors"
                onClick={() => setSelectedEdge(edges[0]!)}>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">Task #{taskId}</Badge>
                    <span className="text-muted-foreground font-normal text-xs">
                      {edges.length} message{edges.length > 1 ? "s" : ""}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="py-0 pb-3">
                  <div className="space-y-2">
                    {edges.map(edge => (
                      <div key={edge.id} className="text-sm pl-3 border-l-2" style={{
                        borderColor: edge.type === "task" ? "#3b82f6" : "#22c55e",
                      }}>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">{displayNames[edge.from] ?? edge.from}</span>
                          <span>&rarr;</span>
                          <span className="font-medium text-foreground">{displayNames[edge.to] ?? edge.to}</span>
                          <Badge variant="outline" className="text-[10px] px-1 py-0">{edge.type}</Badge>
                          <span className="ml-auto">{edge.timestamp}</span>
                        </div>
                        <p className="text-xs mt-1 line-clamp-1">{edge.summary}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Side panel: selected edge details */}
      {selectedEdge && (
        <div className="w-80 border-l bg-muted p-4 overflow-y-auto shrink-0">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-sm">{t("collab.task").replace("{id}", String(selectedEdge.task_id))}</h2>
            <Button variant="outline" size="sm" onClick={() => setSelectedEdge(null)}>&times;</Button>
          </div>
          <div className="space-y-3">
            <div className="bg-card rounded-lg p-3 border-l-4 border-blue-500">
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <span className="font-medium text-foreground">{displayNames[selectedEdge.from] ?? selectedEdge.from}</span>
                <span>&rarr;</span>
                <span className="font-medium text-foreground">{displayNames[selectedEdge.to] ?? selectedEdge.to}</span>
                <Badge variant="outline" className="text-[10px] px-1 py-0 ml-auto">{selectedEdge.type}</Badge>
              </div>
              <div className="text-sm">{selectedEdge.summary}</div>
              <div className="text-xs text-muted-foreground mt-1">{selectedEdge.timestamp}</div>
            </div>
            {selectedEdge.replies?.map((r, i) => (
              <div key={i} className="bg-card rounded-lg p-3 border-l-4 border-green-500">
                <div className="text-xs text-muted-foreground mb-1">
                  <span className="font-medium text-foreground">{displayNames[r.from] ?? r.from}</span>
                  <span className="mx-1">&rarr;</span>
                  <span className="font-medium text-foreground">{displayNames[selectedEdge.from] ?? selectedEdge.from}</span>
                </div>
                <div className="text-sm">{r.content}</div>
                <div className="text-xs text-muted-foreground mt-1">{r.timestamp}</div>
              </div>
            ))}
            {(!selectedEdge.replies || selectedEdge.replies.length === 0) && (
              <p className="text-xs text-muted-foreground">No replies yet</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
