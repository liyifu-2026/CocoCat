import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { BookOpen, Loader2, Upload, X } from "lucide-react"

export default function KnowledgePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [uploadKb, setUploadKb] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ kbName, file }: { kbName: string; file: File }) => {
      const formData = new FormData()
      formData.append("file", file)
      setUploadStatus("Uploading...")
      const res = await fetch(`/api/knowledge/${kbName}/upload`, {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      setUploadStatus(`Queued: ${data.task_uuid?.slice(0, 8) || "ok"}`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] })
    },
  })

  const kbs = (data as { kbs?: { id: string; purpose?: string }[] })?.kbs ?? []

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookOpen className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-bold">知识库</h1>
        </div>
      </div>
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
              className="absolute top-3 right-3 p-1.5 rounded-md bg-muted hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity"
              title="Upload file"
            >
              <Upload className="size-3.5" />
            </button>
          </div>
        ))}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && uploadKb) {
            uploadMutation.mutate({ kbName: uploadKb, file })
          }
          e.target.value = ""
          setUploadKb(null)
        }}
      />

      {uploadStatus && (
        <div className="fixed bottom-4 right-4 bg-card border border-border rounded-lg px-4 py-2 text-sm shadow-lg flex items-center gap-2">
          <span>{uploadStatus}</span>
          <button onClick={() => setUploadStatus("")}><X className="size-3" /></button>
        </div>
      )}
    </div>
  )
}
