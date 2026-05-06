import { useState, useEffect, useRef, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import * as d3 from "d3"
import { api } from "@/api/client"
import { agentsApi } from "@/api/agents"
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

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  color: string
  displayName: string
  r: number
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  source: string | SimNode
  target: string | SimNode
  type: string
  summary: string
  task_id: number
}

const COLORS = [
  "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
]

export default function Collaboration() {
  const t = useT()
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const simRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["collaboration-graph"],
    queryFn: () => api.get<GraphData>("/collaboration/graph"),
    refetchInterval: selectedEdge ? false : 15000,
  })
  const { data: displayData } = useQuery({
    queryKey: ["agent-displays"],
    queryFn: () => agentsApi.listDisplays(),
  })

  const renderGraph = useCallback(() => {
    if (!data || !svgRef.current) return
    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth || 800
    const height = 500

    svg.selectAll("*").remove()
    svg.attr("viewBox", `0 0 ${width} ${height}`)

    const colorMap: Record<string, string> = {}
    data.nodes.forEach((n, i) => { colorMap[n.id] = COLORS[i % COLORS.length]! })

    const nodes: SimNode[] = data.nodes.map(n => {
      const nick = displayData?.[n.id]?.nickname
      return {
        id: n.id,
        label: n.label,
        color: colorMap[n.id] ?? "#3b82f6",
        displayName: nick ? nick : n.label,
        r: 24,
      }
    })

    const links: SimLink[] = data.edges.map(e => ({
      id: e.id,
      source: e.from,
      target: e.to,
      type: e.type,
      summary: e.summary,
      task_id: e.task_id,
    }))

    const g = svg.append("g")

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => { g.attr("transform", event.transform) })
    svg.call(zoom)

    // Arrow markers
    const defs = svg.append("defs")
    defs.append("marker").attr("id", "arrow-task").attr("viewBox", "0 0 10 10")
      .attr("refX", 28).attr("refY", 5).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
      .append("path").attr("d", "M0,0 L10,5 L0,10 Z").attr("fill", "#3b82f6")
    defs.append("marker").attr("id", "arrow-reply").attr("viewBox", "0 0 10 10")
      .attr("refX", 28).attr("refY", 5).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
      .append("path").attr("d", "M0,0 L10,5 L0,10 Z").attr("fill", "#22c55e")

    // Edges
    const linkGroup = g.append("g")
    const linkLines = linkGroup.selectAll<SVGLineElement, SimLink>("line")
      .data(links).join("line")
      .attr("stroke", d => d.type === "task" ? "#3b82f6" : "#22c55e")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", d => d.type === "task" ? "" : "6,3")
      .attr("marker-end", d => `url(#arrow-${d.type === "task" ? "task" : "reply"})`)
      .attr("opacity", 0.5)
      .style("cursor", "pointer")

    // Edge labels
    const edgeLabels = linkGroup.selectAll<SVGTextElement, SimLink>("text")
      .data(links).join("text")
      .text(d => d.summary.substring(0, 25))
      .attr("font-size", 9)
      .attr("fill", "hsl(var(--muted-foreground))")
      .attr("text-anchor", "middle")
      .attr("opacity", 0)

    // Nodes
    const nodeGroup = g.append("g")

    const nodeCircles = nodeGroup.selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes).join("circle")
      .attr("r", d => d.r)
      .attr("fill", d => d.color)
      .style("cursor", "grab")

    const nodeLabels = nodeGroup.selectAll<SVGTextElement, SimNode>("text.name")
      .data(nodes).join("text")
      .attr("class", "name")
      .text(d => d.displayName)
      .attr("text-anchor", "middle")
      .attr("dy", d => d.r + 16)
      .attr("font-size", 11)
      .attr("fill", "hsl(var(--foreground))")
      .attr("font-weight", "bold")

    const nodeInitials = nodeGroup.selectAll<SVGTextElement, SimNode>("text.initials")
      .data(nodes).join("text")
      .attr("class", "initials")
      .text(d => d.displayName.charAt(0))
      .attr("text-anchor", "middle")
      .attr("dy", 5)
      .attr("font-size", 13)
      .attr("fill", "#fff")
      .attr("font-weight", "bold")
      .style("pointer-events", "none")

    // Hover behavior
    nodeCircles.on("mouseenter", function (event, d) {
      setHoveredNode(d.id)
      const connected = new Set<string>([d.id])
      links.forEach(l => {
        const s = typeof l.source === "object" ? l.source.id : l.source
        const t = typeof l.target === "object" ? l.target.id : l.target
        if (s === d.id) connected.add(t)
        if (t === d.id) connected.add(s)
      })
      nodeCircles.attr("opacity", n => connected.has(n.id) ? 1 : 0.2)
      nodeLabels.attr("opacity", n => connected.has(n.id) ? 1 : 0.2)
      nodeInitials.attr("opacity", n => connected.has(n.id) ? 1 : 0.2)
      linkLines.attr("opacity", l => {
        const s = typeof l.source === "object" ? l.source.id : l.source
        const t = typeof l.target === "object" ? l.target.id : l.target
        return (s === d.id || t === d.id) ? 0.9 : 0.1
      })
      edgeLabels.attr("opacity", l => {
        const s = typeof l.source === "object" ? l.source.id : l.source
        const t = typeof l.target === "object" ? l.target.id : l.target
        return (s === d.id || t === d.id) ? 1 : 0
      })
    }).on("mouseleave", () => {
      setHoveredNode(null)
      nodeCircles.attr("opacity", 1)
      nodeLabels.attr("opacity", 1)
      nodeInitials.attr("opacity", 1)
      linkLines.attr("opacity", 0.5)
      edgeLabels.attr("opacity", 0)
    })

    // Click edge to show details
    linkLines.on("click", (event, d) => {
      const edge = data.edges.find(e => e.id === d.id)
      if (edge) setSelectedEdge(edge)
    })

    // Drag behavior
    const drag = d3.drag<SVGCircleElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
        nodeCircles.style("cursor", "grabbing")
      })
      .on("drag", (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0)
        d.fx = null
        d.fy = null
        nodeCircles.style("cursor", "grab")
      })
    nodeCircles.call(drag)

    // Force simulation
    const sim = d3.forceSimulation<SimNode>(nodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id(d => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-250))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide<SimNode>().radius(d => d.r + 30))
      .on("tick", () => {
        linkLines.attr("x1", d => (d.source as SimNode).x!)
          .attr("y1", d => (d.source as SimNode).y!)
          .attr("x2", d => (d.target as SimNode).x!)
          .attr("y2", d => (d.target as SimNode).y!)
        edgeLabels.attr("x", d => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
          .attr("y", d => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2 - 6)
        nodeCircles.attr("cx", d => d.x!).attr("cy", d => d.y!)
        nodeLabels.attr("x", d => d.x!).attr("y", d => d.y!)
        nodeInitials.attr("x", d => d.x!).attr("y", d => d.y!)
      })

    simRef.current = sim
  }, [data, displayData])

  useEffect(() => { renderGraph() }, [renderGraph])

  // Cleanup simulation on unmount
  useEffect(() => {
    return () => { simRef.current?.stop() }
  }, [])

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
            <Button variant="outline" size="sm" onClick={() => renderGraph()}>
              Reset
            </Button>
          </div>
        </div>
        <svg ref={svgRef} className="w-full border rounded bg-card" style={{ height: 500 }} />
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
