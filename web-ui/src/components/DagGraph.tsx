import { useEffect, useRef } from "react"
import * as d3 from "d3"
import dagre from "dagre"

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

const statusColor = (status: string): string => {
  switch (status) {
    case "done": return "#22c55e"
    case "running": return "#3b82f6"
    case "pending": return "#94a3b8"
    case "failed": return "#ef4444"
    default: return "#94a3b8"
  }
}

const statusBg = (status: string): string => {
  switch (status) {
    case "done": return "#f0fdf4"
    case "running": return "#eff6ff"
    case "pending": return "#f8fafc"
    case "failed": return "#fef2f2"
    default: return "#f8fafc"
  }
}

interface GraphNode {
  id: string
  label: string
  stageId: string
  status: string
  isStage: boolean
  parallel?: boolean
  depends_on?: string[]
}

export default function DagGraph({ run }: { run: DagRun }) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || !run.stages?.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()

    const nodes: GraphNode[] = []
    const edges: { from: string; to: string }[] = []

    for (const stage of run.stages) {
      nodes.push({
        id: stage.id,
        label: stage.name || stage.id,
        stageId: stage.id,
        status: stage.status || "pending",
        isStage: true,
        parallel: stage.parallel,
        depends_on: stage.depends_on,
      })

      for (const task of stage.tasks || []) {
        nodes.push({
          id: `${stage.id}/${task.id}`,
          label: task.id,
          stageId: stage.id,
          status: task.status,
          isStage: false,
        })
        edges.push({ from: stage.id, to: `${stage.id}/${task.id}` })
      }

      if (stage.depends_on) {
        for (const dep of stage.depends_on) {
          edges.push({ from: dep, to: stage.id })
        }
      }
    }

    const g = new dagre.graphlib.Graph()
    g.setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: "TB", nodesep: 20, ranksep: 60, marginx: 20, marginy: 20 })

    for (const node of nodes) {
      g.setNode(node.id, {
        width: node.isStage ? 150 : 120,
        height: node.isStage ? 44 : 36,
      })
    }

    for (const edge of edges) {
      g.setEdge(edge.from, edge.to)
    }

    dagre.layout(g)

    const firstNode = g.node(nodes[0]?.id ?? "")
    const graphWidth = (g.graph().width || 600) + 40
    const graphHeight = (g.graph().height || 400) + 40

    svg.attr("viewBox", `0 0 ${graphWidth} ${graphHeight}`)
       .attr("width", "100%")
       .attr("height", graphHeight)

    const defs = svg.append("defs")

    defs.append("marker")
      .attr("id", `arrow-${run.run_id}`)
      .attr("viewBox", "0 0 10 10")
      .attr("refX", 10)
      .attr("refY", 5)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M 0 0 L 10 5 L 0 10 z")
      .attr("fill", "#cbd5e1")

    svg.append("g")
      .selectAll("line")
      .data(edges)
      .enter()
      .append("path")
      .attr("d", d => {
        const from = g.node(d.from)
        const to = g.node(d.to)
        const fromNode = nodes.find(n => n.id === d.from)
        const fromH = fromNode?.isStage ? 44 : 36
        return `M ${from.x} ${from.y + fromH / 2} L ${to.x} ${to.y - 18}`
      })
      .attr("stroke", "#cbd5e1")
      .attr("stroke-width", 1.5)
      .attr("fill", "none")
      .attr("marker-end", `url(#arrow-${run.run_id})`)

    const nodeGroups = svg.append("g")
      .selectAll("g")
      .data(nodes)
      .enter()
      .append("g")
      .attr("transform", d => {
        const node = g.node(d.id)
        return `translate(${node.x - node.width / 2}, ${node.y - node.height / 2})`
      })

    if (nodes.some(n => n.isStage)) {
      nodeGroups
        .filter(d => d.isStage)
        .append("rect")
        .attr("width", d => 150)
        .attr("height", 44)
        .attr("rx", 10)
        .attr("ry", 10)
        .attr("fill", d => statusBg(d.status))
        .attr("stroke", d => statusColor(d.status))
        .attr("stroke-width", 2)

      nodeGroups
        .filter(d => d.isStage)
        .append("text")
        .attr("x", 75)
        .attr("y", 26)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .attr("font-weight", "600")
        .attr("fill", "#334155")
        .text(d => {
          const prefix = d.parallel ? "∥ " : ""
          return prefix + d.label
        })
    }

    nodeGroups
      .filter(d => !d.isStage)
      .append("rect")
      .attr("width", 120)
      .attr("height", 36)
      .attr("rx", 8)
      .attr("ry", 8)
      .attr("fill", d => statusBg(d.status))
      .attr("stroke", d => statusColor(d.status))
      .attr("stroke-width", 1.5)

    nodeGroups
      .filter(d => !d.isStage)
      .append("text")
      .attr("x", 60)
      .attr("y", 22)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("font-family", "monospace")
      .attr("fill", "#475569")
      .text(d => d.label)
  }, [run])

  return (
    <div className="rounded-xl border border-border/60 bg-background overflow-auto">
      <svg ref={svgRef} className="w-full" style={{ minHeight: 200 }} />
    </div>
  )
}
