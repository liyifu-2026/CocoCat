import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { Plus, Play, Pause, Archive, Trash2, Edit3, MessageSquare } from "lucide-react"

interface Scene {
  id: string
  name: string
  description: string
  status: string
  purpose: string
  kbs: string[]
  skills: string[]
  channels: string[]
  agent?: { name: string }
  created_at: string
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  running: { label: "运行中", className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" },
  paused: { label: "已暂停", className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" },
  archived: { label: "已归档", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" },
}

export default function ScenesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: scenes = [] } = useQuery<Scene[]>({
    queryKey: ["scenes"],
    queryFn: async () => {
      const res = await fetch("/api/scenes")
      if (!res.ok) throw new Error("Failed to load scenes")
      const data = await res.json()
      return Array.isArray(data) ? data : (data.scenes ?? [])
    },
  })

  const handleLifecycle = async (id: string, action: string) => {
    await fetch(`/api/scenes/${id}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
    queryClient.invalidateQueries({ queryKey: ["scenes"] })
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">场景</h1>
        <button
          onClick={() => navigate("/scenes/new")}
          className="flex items-center gap-2 bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors"
        >
          <Plus size={18} /> 新建场景
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {scenes.map((scene) => {
          const statusInfo = STATUS_LABELS[scene.status] ?? {
            label: scene.status,
            className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
          }
          const isArchived = scene.status === "archived"
          return (
            <div
              key={scene.id}
              className={`border rounded-xl p-5 hover:shadow-md transition-shadow bg-card ${
                isArchived ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-lg">{scene.name}</h3>
                <span className={`text-xs px-2 py-1 rounded-full ${statusInfo.className}`}>
                  {statusInfo.label}
                </span>
              </div>
              {scene.description && (
                <p className="text-sm text-muted-foreground mb-3">{scene.description}</p>
              )}
              <div className="flex flex-wrap gap-2 mb-3">
                {scene.agent && (
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    {scene.agent.name}
                  </span>
                )}
                {scene.kbs?.map((kb: string) => (
                  <span key={kb} className="text-xs bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400 px-2 py-0.5 rounded">
                    📚 {kb}
                  </span>
                ))}
                {scene.channels?.map((ch: string) => (
                  <span key={ch} className="text-xs bg-teal-50 text-teal-600 dark:bg-teal-900/20 dark:text-teal-400 px-2 py-0.5 rounded">
                    {ch === "web" ? "🌐 Web" : ch}
                  </span>
                ))}
              </div>
              <div className="flex gap-3">
                {scene.status === "running" && (
                  <>
                    <button onClick={() => navigate(`/scenes/${scene.id}/run`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <MessageSquare size={14} /> 聊天
                    </button>
                    <button onClick={() => navigate(`/scenes/${scene.id}`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Edit3 size={14} /> 编辑
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "pause")} className="text-sm text-yellow-500 hover:text-yellow-700 flex items-center gap-1">
                      <Pause size={14} /> 暂停
                    </button>
                  </>
                )}
                {scene.status === "paused" && (
                  <>
                    <button onClick={() => handleLifecycle(scene.id, "resume")} className="text-sm text-green-500 hover:text-green-700 flex items-center gap-1">
                      <Play size={14} /> 恢复
                    </button>
                    <button onClick={() => navigate(`/scenes/${scene.id}`)} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Edit3 size={14} /> 编辑
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "archive")} className="text-sm text-blue-500 hover:text-blue-700 flex items-center gap-1">
                      <Archive size={14} /> 归档
                    </button>
                  </>
                )}
                {scene.status === "archived" && (
                  <>
                    <button onClick={() => handleLifecycle(scene.id, "resume")} className="text-sm text-green-500 hover:text-green-700 flex items-center gap-1">
                      <Play size={14} /> 恢复
                    </button>
                    <button onClick={() => handleLifecycle(scene.id, "delete")} className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1">
                      <Trash2 size={14} /> 删除
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })}
        <button
          onClick={() => navigate("/scenes/new")}
          className="border-2 border-dashed border-border rounded-xl p-5 flex items-center justify-center min-h-[120px] hover:border-blue-300 hover:bg-blue-50/50 dark:hover:bg-blue-950/30 transition-colors"
        >
          <div className="text-center">
            <Plus size={28} className="mx-auto text-muted-foreground" />
            <p className="text-sm text-muted-foreground mt-2">新建场景</p>
          </div>
        </button>
      </div>
    </div>
  )
}
