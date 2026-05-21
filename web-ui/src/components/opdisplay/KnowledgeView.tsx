import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { BookOpen, Loader2, Upload, Plus, FileText, X, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

export default function KnowledgeView() {
  const queryClient = useQueryClient()
  const [uploadKb, setUploadKb] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newKbName, setNewKbName] = useState("")
  const [newKbPurpose, setNewKbPurpose] = useState("")
  const [createError, setCreateError] = useState("")

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ kbName, file }: { kbName: string; file: File }) => {
      setUploading(true)
      setUploadStatus(`Uploading ${file.name}...`)
      const formData = new FormData()
      formData.append("file", file)
      const res = await fetch(`/api/knowledge/${kbName}/upload`, { method: "POST", body: formData })
      const data = await res.json()
      setUploadStatus(`${file.name} queued (${data.task_uuid?.slice(0, 8) || "ok"})`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] })
      setTimeout(() => { setUploading(false); setUploadStatus("") }, 4000)
    },
    onError: () => {
      setUploadStatus("Upload failed")
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
        throw new Error(data.error || "Create failed")
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
      setCreateError((err as Error).message === "409" ? "KB already exists" : (err as Error).message)
    },
  })

  if (isLoading) {
    return (
      <div className="flex flex-col h-full animate-view-enter">
        <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
          <BookOpen className="size-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold">Knowledge Base</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[52px] w-full rounded-xl shimmer-skeleton" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full animate-view-enter gap-3">
        <p className="text-[11px] text-muted-foreground">Failed to load knowledge bases</p>
        <button onClick={() => refetch()} className="flex items-center gap-1.5 text-[10px] text-primary hover:underline">
          <RefreshCw className="size-3" /> Retry
        </button>
      </div>
    )
  }

  const kbs = (data as { kbs?: { id: string; purpose?: string }[] })?.kbs ?? []

  return (
    <div className="flex flex-col h-full animate-view-enter">
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
        <BookOpen className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">Knowledge Base</h2>
        <div className="flex-1" />
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded-lg border border-border bg-card hover:bg-muted transition-colors"
        >
          <Plus className="size-3" /> New KB
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showCreateForm && (
          <div className="bg-card border border-border rounded-xl p-4">
            <form onSubmit={e => { e.preventDefault(); if (newKbName.trim()) { setCreateError(""); createKbMutation.mutate({ name: newKbName.trim(), purpose: newKbPurpose.trim() }) } }} className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium text-muted-foreground">Create Knowledge Base</span>
                <button type="button" onClick={() => setShowCreateForm(false)}><X className="size-3.5 text-muted-foreground" /></button>
              </div>
              <input autoFocus value={newKbName} onChange={e => setNewKbName(e.target.value)} placeholder="KB name" className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary" />
              <textarea value={newKbPurpose} onChange={e => setNewKbPurpose(e.target.value)} placeholder="Purpose (optional)" rows={2} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary resize-none" />
              {createError && <p className="text-[10px] text-destructive">{createError}</p>}
              <button type="submit" disabled={!newKbName.trim() || createKbMutation.isPending} className="rounded-lg bg-primary px-4 py-1.5 text-[10px] font-medium text-primary-foreground disabled:opacity-50 flex items-center gap-1.5">
                {createKbMutation.isPending && <Loader2 className="size-3 animate-spin" />} Create
              </button>
            </form>
          </div>
        )}

        {kbs.length === 0 && !showCreateForm && (
          <p className="text-[11px] text-muted-foreground text-center py-8">No knowledge bases yet</p>
        )}

        <div className="grid gap-2.5">
          {kbs.map(kb => (
            <div key={kb.id} className="group flex items-center justify-between bg-card border border-border rounded-xl px-4 py-3 hover:border-primary/20 transition-colors">
              <div>
                <div className="text-xs font-medium">{kb.id}</div>
                {kb.purpose && <div className="text-[10px] text-muted-foreground line-clamp-1">{kb.purpose}</div>}
              </div>
              <button
                onClick={() => { setUploadKb(kb.id); fileInputRef.current?.click() }}
                disabled={uploading}
                className="p-1.5 rounded-lg bg-muted hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Upload className="size-3.5" />
              </button>
            </div>
          ))}
        </div>

        {kbs.length > 0 && (
          <div className="border border-dashed border-border rounded-xl p-4 text-center cursor-pointer hover:border-primary/30 transition-colors">
            <FileText className="size-4 text-muted-foreground/40 mx-auto mb-1" />
            <p className="text-[9px] text-muted-foreground/50">Drop files here or click to upload</p>
          </div>
        )}

        {uploadStatus && (
          <div className={cn("flex items-center gap-2 text-[10px] px-3 py-2 rounded-lg", uploading ? "bg-accent/10 text-accent" : "bg-emerald-500/10 text-emerald-400")}>
            {uploading && <Loader2 className="size-3 animate-spin" />}
            {uploadStatus}
          </div>
        )}
      </div>

      <input ref={fileInputRef} type="file" className="hidden" onChange={e => {
        const file = e.target.files?.[0]
        const kb = uploadKb || kbs[0]?.id
        if (file && kb) uploadMutation.mutate({ kbName: kb, file })
        e.target.value = ""
        setUploadKb(null)
      }} />
    </div>
  )
}
