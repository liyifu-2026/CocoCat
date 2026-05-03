import { useState, useEffect, useRef } from "react";
import dagre from "dagre";

interface GraphNode {
  id: string;
  label: string;
}

interface ReplyInfo {
  from: string;
  content: string;
  timestamp: string;
}

interface GraphEdge {
  id: string;
  from: string;
  to: string;
  task_id: number;
  type: string;
  summary: string;
  timestamp: string;
  replies: ReplyInfo[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface DagreNode {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface DagrePoint {
  x: number;
  y: number;
}

interface DagreEdge {
  points: DagrePoint[];
}

export default function Collaboration() {
  const [data, setData] = useState<GraphData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await fetch("/api/collaboration/graph");
        const json: GraphData = await resp.json();
        setData(json);
      } catch { /* ignore polling errors */ }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  }

  if (data.nodes.length === 0) {
    return <div className="p-8 text-gray-500">No collaboration data yet. Run a task dispatch first.</div>;
  }

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 50, ranksep: 80, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  data.nodes.forEach((n) => g.setNode(n.id, { width: 140, height: 50, label: n.label }));
  data.edges.forEach((e) => g.setEdge(e.from, e.to, { id: e.id }));

  dagre.layout(g);

  const nodePositions: Record<string, DagreNode> = {};
  g.nodes().forEach((id: string) => {
    const node = g.node(id);
    nodePositions[id] = { x: node.x - 70, y: node.y - 25, width: 140, height: 50 };
  });

  const edgePaths: Record<string, DagreEdge> = {};
  g.edges().forEach((e: { v: string; w: string }) => {
    const edge = g.edge(e);
    edgePaths[`${e.v}->${e.w}`] = { points: edge.points || [] };
  });

  const padding = 60;
  const xs = Object.values(nodePositions).map((n) => [n.x, n.x + n.width]).flat();
  const ys = Object.values(nodePositions).map((n) => [n.y, n.y + n.height]).flat();
  const svgWidth = Math.max(800, (xs.length ? Math.max(...xs) : 800) + padding);
  const svgHeight = Math.max(400, (ys.length ? Math.max(...ys) : 400) + padding);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto p-4">
        <h1 className="text-lg font-semibold mb-4">Collaboration Graph</h1>
        <svg ref={svgRef} width={svgWidth} height={svgHeight} className="border rounded bg-white">
          <defs>
            <marker id="arrow-task" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 Z" fill="#3b82f6" />
            </marker>
            <marker id="arrow-reply" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 Z" fill="#22c55e" />
            </marker>
          </defs>

          {data.edges.map((edge) => {
            const ep = edgePaths[`${edge.from}->${edge.to}`];
            if (!ep || !ep.points || ep.points.length < 2) return null;
            const isTask = edge.type === "task";
            const mid = ep.points[Math.floor(ep.points.length / 2)];
            const d = ep.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
            return (
              <g key={edge.id}>
                <path
                  d={d}
                  fill="none"
                  stroke={isTask ? "#3b82f6" : "#22c55e"}
                  strokeWidth={2}
                  strokeDasharray={isTask ? "" : "6,3"}
                  markerEnd={`url(#arrow-${isTask ? "task" : "reply"})`}
                  className="cursor-pointer"
                  style={{ opacity: 0.7, transition: "opacity 0.2s" }}
                  onClick={() => setSelectedEdge(edge)}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.7")}
                />
                {mid && (
                  <text x={mid.x} y={mid.y - 8} textAnchor="middle" fontSize={10} fill="#6b7280"
                        className="pointer-events-none select-none">
                    {edge.summary.substring(0, 20)}
                  </text>
                )}
              </g>
            );
          })}

          {data.nodes.map((node) => {
            const pos = nodePositions[node.id];
            if (!pos) return null;
            return (
              <g key={node.id} className="cursor-default">
                <rect x={pos.x} y={pos.y} width={pos.width} height={pos.height}
                      rx={8} ry={8} fill="#eff6ff" stroke="#3b82f6" strokeWidth={2} />
                <text x={pos.x + 70} y={pos.y + 20} textAnchor="middle" fontSize={13}
                      fontWeight="bold" fill="#1e40af">
                  {node.label}
                </text>
                <text x={pos.x + 70} y={pos.y + 36} textAnchor="middle" fontSize={10}
                      fill="#6b7280">
                  {node.id}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {selectedEdge && (
        <div className="w-80 border-l bg-gray-50 p-4 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">Task #{selectedEdge.task_id}</h2>
            <button onClick={() => setSelectedEdge(null)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
          </div>
          <div className="space-y-3">
            <div className="bg-white rounded p-3 border-l-4 border-blue-500">
              <div className="text-xs text-gray-500 mb-1">
                {selectedEdge.from} &rarr; {selectedEdge.to} <span className="italic">(task)</span>
              </div>
              <div className="text-sm">{selectedEdge.summary}</div>
              <div className="text-xs text-gray-400 mt-1">{selectedEdge.timestamp}</div>
            </div>
            {selectedEdge.replies.map((r, i) => (
              <div key={i} className="bg-white rounded p-3 border-l-4 border-green-500">
                <div className="text-xs text-gray-500 mb-1">
                  {r.from} &rarr; {selectedEdge.from} <span className="italic">(reply)</span>
                </div>
                <div className="text-sm">{r.content}</div>
                <div className="text-xs text-gray-400 mt-1">{r.timestamp}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
