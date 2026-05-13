import { useState, useEffect } from "react"
import { useParams } from "react-router-dom"
import { Loader2, Plus } from "lucide-react"

interface SceneData {
  id: string
  name?: string
  kbs?: string[]
  skills?: string[]
}

export default function SceneDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const abort = new AbortController()
    const load = async () => {
      setLoading(true)
      try {
        const r = await fetch(`/api/scenes/${id}`, { signal: abort.signal })
        const data = await r.json()
        if (!abort.signal.aborted) setScene(data)
      } catch {
        // ignore aborted or failed requests
      } finally {
        if (!abort.signal.aborted) setLoading(false)
      }
    }
    load()
    return () => abort.abort()
  }, [id])

  if (loading) return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  if (!scene) return <div className="p-6 text-muted-foreground">Scene not found: {id}</div>

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">{scene.name || scene.id}</h1>
          <span className="text-xs text-muted-foreground">
            {scene.kbs?.length || 0} KBs · {scene.skills?.length || 0} Skills
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 text-center text-muted-foreground">
        <p>Channel messages will appear here.</p>
        <p className="text-xs mt-2">
          Connect channels via Settings → 渠道
        </p>
      </div>

      <div className="border-t px-4 py-2 flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">📚 KB:</span>
          {(scene.kbs || []).length === 0
            ? <span className="text-muted-foreground text-xs">None</span>
            : (scene.kbs || []).map((kb: string) => (
                <span key={kb} className="rounded bg-muted px-2 py-0.5 text-xs">{kb}</span>
              ))}
          <button className="text-muted-foreground hover:text-foreground ml-1" title="Add KB" onClick={() => {}}>
            <Plus className="size-3" />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">🔧 Skills:</span>
          {(scene.skills || []).length === 0
            ? <span className="text-muted-foreground text-xs">None</span>
            : (scene.skills || []).map((s: string) => (
                <span key={s} className="rounded bg-muted px-2 py-0.5 text-xs">{s}</span>
              ))}
          <button className="text-muted-foreground hover:text-foreground ml-1" title="Add Skill" onClick={() => {}}>
            <Plus className="size-3" />
          </button>
        </div>
      </div>
    </div>
  )
}
