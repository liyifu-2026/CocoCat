import { useState, useRef, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronDown, ChevronUp, Upload, FileText, X, Loader2, Send } from "lucide-react"

interface RawFile {
  name: string
  size: number
}

export default function RawZone() {
  const [expanded, setExpanded] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data: rawFiles } = useQuery({
    queryKey: ["raw-files"],
    queryFn: () => fetch("/api/knowledge/.raw").then(r => r.json()),
    enabled: expanded,
  })

  const files: RawFile[] = (rawFiles as any)?.files ?? []

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  const handleUpload = useCallback(async (fileList: FileList | null) => {
    if (!fileList?.length) return
    setUploading(true)
    for (const file of Array.from(fileList)) {
      const formData = new FormData()
      formData.append("file", file)
      await fetch("/api/knowledge/.raw/upload", { method: "POST", body: formData })
    }
    queryClient.invalidateQueries({ queryKey: ["raw-files"] })
    setUploading(false)
  }, [queryClient])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    handleUpload(e.dataTransfer.files)
  }, [handleUpload])

  const handleDelete = async (filename: string) => {
    await fetch(`/api/knowledge/.raw/${encodeURIComponent(filename)}`, { method: "DELETE" })
    queryClient.invalidateQueries({ queryKey: ["raw-files"] })
  }

  return (
    <div className="border-t border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Upload className="size-3.5 text-muted-foreground" />
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Raw Staging
          </span>
          {files.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">{files.length}</span>
          )}
        </div>
        {expanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronUp className="size-3.5 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2">
          <div
            className="border border-dashed border-border rounded-xl p-3 text-center cursor-pointer hover:border-primary/30 transition-colors"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-[10px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Uploading...
              </div>
            ) : (
              <>
                <FileText className="size-4 text-muted-foreground/40 mx-auto mb-1" />
                <p className="text-[10px] text-muted-foreground/50">Drop files or click to upload</p>
              </>
            )}
          </div>

          {files.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {files.map(f => (
                <div key={f.name} className="flex items-center gap-2 bg-card border border-border rounded-lg px-2.5 py-1.5 text-[10px]">
                  <FileText className="size-3 text-muted-foreground" />
                  <span className="max-w-[120px] truncate">{f.name}</span>
                  <span className="text-muted-foreground/50">{formatSize(f.size)}</span>
                  <button onClick={() => handleDelete(f.name)} className="text-muted-foreground hover:text-red-400">
                    <X className="size-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {files.length > 0 && (
            <button
              onClick={() => {
                window.dispatchEvent(new CustomEvent("raw-organize", { detail: { files } }))
              }}
              className="w-full flex items-center justify-center gap-1.5 bg-primary/10 text-primary text-[10px] font-medium py-2 rounded-lg hover:bg-primary/20 transition-colors"
            >
              <Send className="size-3" />
              Ask agent to organize
            </button>
          )}

          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={e => { handleUpload(e.target.files); e.target.value = "" }}
          />
        </div>
      )}
    </div>
  )
}
