import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { BookOpen, Loader2, Upload, X, FileText, Plus } from "lucide-react"
import KbChatPanel from "@/components/KbChatPanel"

export default function KnowledgePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [uploadKb, setUploadKb] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newKbName, setNewKbName] = useState("")
  const [newKbPurpose, setNewKbPurpose] = useState("")
  const [createError, setCreateError] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ kbName, file }: { kbName: string; file: File }) => {
      setUploading(true)
      setUploadStatus(`正在上传 ${file.name}...`)
      const formData = new FormData()
      formData.append("file", file)
      const res = await fetch(`/api/knowledge/${kbName}/upload`, {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      setUploadStatus(`${file.name} 已加入队列 (${data.task_uuid?.slice(0, 8) || "ok"})，kb-agent 即将处理`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] })
      setTimeout(() => { setUploading(false); setUploadStatus("") }, 4000)
    },
    onError: () => {
      setUploadStatus("上传失败")
      setTimeout(() => { setUploading(false); setUploadStatus("") }, 3000)
    },
  })

  const createKbMutation = useMutation({
    mutationFn: async ({ name, purpose }: { name: string; purpose: string }) => {
      const res = await fetch("/api/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, purpose }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        if (res.status === 409) throw new Error("409")
        throw new Error(data.error || "创建失败")
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] })
      setShowCreateForm(false)
      setNewKbName("")
      setNewKbPurpose("")
      setCreateError("")
    },
    onError: (err) => {
      if ((err as Error).message === "409") {
        setCreateError("知识库已存在")
      } else {
        setCreateError((err as Error).message)
      }
    },
  })

  const kbs = (data as { kbs?: { id: string; purpose?: string }[] })?.kbs ?? []

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top: KB cards */}
      <div className="flex-1 overflow-y-auto p-6 pb-0">
        <div className="flex items-center gap-3 mb-4">
          <BookOpen className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-bold">知识库</h1>
          <div className="flex-1" />
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-accent transition-colors"
          >
            <Plus className="size-4" />
            创建知识库
          </button>
        </div>
        {showCreateForm && (
          <div className="mb-6 rounded-xl border border-border/60 bg-card p-4">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!newKbName.trim()) return
                setCreateError("")
                createKbMutation.mutate({ name: newKbName.trim(), purpose: newKbPurpose.trim() })
              }}
              className="space-y-3"
            >
              <input
                autoFocus
                value={newKbName}
                onChange={(e) => setNewKbName(e.target.value)}
                placeholder="知识库名称"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <textarea
                value={newKbPurpose}
                onChange={(e) => setNewKbPurpose(e.target.value)}
                placeholder="用途说明 (可选)"
                rows={2}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
              />
              {createError && (
                <p className="text-xs text-red-500">{createError}</p>
              )}
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="submit"
                  disabled={!newKbName.trim() || createKbMutation.isPending}
                  className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-opacity inline-flex items-center gap-1.5"
                >
                  {createKbMutation.isPending && <Loader2 className="size-3.5 animate-spin" />}
                  创建
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false)
                    setNewKbName("")
                    setNewKbPurpose("")
                    setCreateError("")
                  }}
                  className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        )}
        {kbs.length === 0 && (
          <p className="text-sm text-muted-foreground">暂无知识库</p>
        )}
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {kbs.map(kb => (
            <div key={kb.id} className="relative group">
              <button
                onClick={() => navigate(`/knowledge/${kb.id}`)}
                className="w-full rounded-xl border border-border/60 bg-card p-5 text-left hover:shadow-sm transition-shadow duration-200 space-y-2"
              >
                <h3 className="font-medium">{kb.id}</h3>
                {kb.purpose && <p className="text-xs text-muted-foreground line-clamp-3">{kb.purpose}</p>}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setUploadKb(kb.id)
                  fileInputRef.current?.click()
                }}
                disabled={uploading}
                className="absolute top-3 right-3 p-1.5 rounded-md bg-muted hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50"
                title="上传文件"
              >
                <Upload className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom: Upload + Chat */}
      <div className="border-t border-border flex h-[320px] shrink-0">
        {/* Left: Upload area */}
        <div className="w-72 border-r border-border p-4 flex flex-col">
          <h3 className="text-xs font-medium text-muted-foreground mb-3 flex items-center gap-1.5">
            <FileText className="size-3.5" />
            上传材料
          </h3>
          <div
            className="flex-1 border-2 border-dashed border-border rounded-xl flex flex-col items-center justify-center gap-2 text-muted-foreground cursor-pointer hover:border-primary/50 hover:text-primary transition-colors"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              const file = e.dataTransfer.files?.[0]
              const kb = kbs[0]
              if (file && kb) {
                uploadMutation.mutate({ kbName: kb.id, file })
              }
            }}
          >
            <Upload className="size-6 opacity-40" />
            <p className="text-xs">拖拽文件到此处</p>
            <p className="text-[10px] opacity-50">或点击选择文件</p>
          </div>
          {uploadStatus && (
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              {uploading && <Loader2 className="size-3 animate-spin" />}
              <span>{uploadStatus}</span>
            </div>
          )}
          {uploadKb && (
            <p className="text-[10px] text-muted-foreground mt-1">
              目标 KB: {uploadKb}
            </p>
          )}
        </div>
        {/* Right: Chat panel */}
        <div className="flex-1">
          <KbChatPanel kbName={kbs[0]?.id || ""} />
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          const kb = uploadKb || kbs[0]?.id
          if (file && kb) {
            uploadMutation.mutate({ kbName: kb, file })
          }
          e.target.value = ""
          setUploadKb(null)
        }}
      />
    </div>
  )
}
