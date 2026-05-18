import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Settings, Pause, X } from "lucide-react"

interface SceneFull {
  id: string
  name: string
  description: string
  status: string
  agent?: { id: string; name: string; tone: string; language: string; personality: string }
  kbs: string[]
  skills: string[]
  channels: string[]
}

const TONE_LABELS: Record<string, string> = {
  friendly: "😊 亲切友好",
  professional: "👔 专业严谨",
  concise: "⚡ 简洁高效",
  humorous: "🎭 幽默风趣",
}

const LANGUAGE_LABELS: Record<string, string> = {
  zh: "中文",
  en: "English",
  zh_en: "中英混合",
}

export default function SceneRun() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState("")
  const [showConfig, setShowConfig] = useState(false)

  const { data: scene } = useQuery<SceneFull>({
    queryKey: ["scene", id],
    queryFn: async () => {
      const res = await fetch(`/api/scenes/${id}`)
      if (!res.ok) throw new Error("Scene not found")
      return res.json()
    },
  })

  const sendMessage = async () => {
    if (!input.trim()) return
    setMessages((m) => [...m, { role: "user", content: input }])
    setInput("")
    setMessages((m) => [...m, { role: "assistant", content: "（Agent 响应区域 — 待接入真实 Agent 系统）" }])
  }

  const handlePause = async () => {
    if (!id) return
    await fetch(`/api/scenes/${id}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: scene?.status === "running" ? "pause" : "resume" }),
    })
    queryClient.invalidateQueries({ queryKey: ["scene", id] })
    queryClient.invalidateQueries({ queryKey: ["scenes"] })
  }

  if (!scene) return <div className="p-6 text-muted-foreground">Loading...</div>

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="border-b border-border px-4 py-3 flex items-center gap-3 shrink-0">
          <button onClick={() => navigate("/scenes")} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft size={20} />
          </button>
          <h2 className="font-semibold truncate">{scene.name}</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
            scene.status === "running"
              ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
          }`}>
            {scene.status === "running" ? "▶ 运行中" : "⏸ 已暂停"}
          </span>
          <button onClick={() => setShowConfig(!showConfig)} className="ml-auto text-muted-foreground hover:text-foreground">
            <Settings size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground mt-20">
              <p className="text-lg">👋 开始和 {scene.agent?.name || scene.name} 对话吧</p>
              {scene.description && <p className="text-sm mt-1">{scene.description}</p>}
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-blue-500 text-white ml-auto"
                  : "bg-muted"
              }`}
            >
              {m.content}
            </div>
          ))}
        </div>
        <div className="border-t border-border p-3 flex gap-2 shrink-0">
          <input
            className="flex-1 border border-border rounded-lg px-3 py-2 text-sm bg-background"
            placeholder="输入消息..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />
          <button
            onClick={sendMessage}
            className="bg-blue-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-600 transition-colors"
          >
            发送
          </button>
        </div>
      </div>

      {/* Config side panel */}
      {showConfig && (
        <div className="w-72 border-l border-border bg-card p-4 overflow-y-auto shrink-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm">⚙ 场景设置</h3>
            <button onClick={() => setShowConfig(false)} className="text-muted-foreground hover:text-foreground">
              <X size={16} />
            </button>
          </div>
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-muted-foreground text-xs">Agent</p>
              <p className="font-medium">{scene.agent?.name || "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">风格</p>
              <p>{TONE_LABELS[scene.agent?.tone ?? ""] || scene.agent?.tone || "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">语言</p>
              <p>{LANGUAGE_LABELS[scene.agent?.language ?? ""] || scene.agent?.language || "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">知识库</p>
              {scene.kbs?.length ? (
                scene.kbs.map((k: string) => <p key={k}>📚 {k}</p>)
              ) : (
                <p className="text-muted-foreground">无</p>
              )}
            </div>
            <div>
              <p className="text-muted-foreground text-xs">技能</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {scene.skills?.length ? (
                  scene.skills.map((s: string) => (
                    <span key={s} className="text-xs bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 px-2 py-0.5 rounded-full">
                      {s}
                    </span>
                  ))
                ) : (
                  <span className="text-muted-foreground">无</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">渠道</p>
              {scene.channels?.length ? (
                scene.channels.map((ch: string) => <p key={ch}>{ch}</p>)
              ) : (
                <p className="text-muted-foreground">无</p>
              )}
            </div>
          </div>
          <div className="mt-6 space-y-2">
            <button
              onClick={() => navigate(`/scenes/${id}`)}
              className="w-full text-sm text-blue-500 border border-blue-500 rounded-lg py-2 hover:bg-blue-50 dark:hover:bg-blue-950/30 transition-colors"
            >
              编辑场景
            </button>
            <button
              onClick={handlePause}
              className="w-full text-sm text-amber-500 border border-amber-300 rounded-lg py-2 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors flex items-center justify-center gap-1"
            >
              <Pause size={14} />
              {scene.status === "running" ? "暂停场景" : "恢复运行"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
