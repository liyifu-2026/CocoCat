import { useState, useEffect, Fragment } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Pencil } from "lucide-react"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AgentAvatar } from "@/components/AgentAvatar"
import ErrorState from "@/components/ErrorState"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"

export default function Agents() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [nicknameInput, setNicknameInput] = useState("")
  const [displayConfs, setDisplayConfs] = useState<Record<string, {nickname?: string}>>({})

  useEffect(() => {
    if (!data?.agents) return
    data.agents.forEach(async (a) => {
      try {
        const d = await agentsApi.display(a.id)
        if (d?.nickname) setDisplayConfs(p => ({ ...p, [a.id]: { nickname: d.nickname } }))
      } catch {}
    })
  }, [data])

  if (isLoading) return <CardGridSkeleton count={6} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Agents</h1>
      {!data?.agents?.length ? (
        <p className="text-muted-foreground">No agents found.</p>
      ) : (
        <div>
          {data.agents.map(a => (
            <Fragment key={a.id}>
              <div className="flex items-center gap-3 p-3">
                <AgentAvatar name={displayConfs[a.id]?.nickname || a.name} size="sm"
                  status={a.status === "running" ? "idle" : a.status === "error" ? "busy" : undefined} />
                <div className="flex-1">
                  <p className="font-medium flex items-center gap-1">
                    {displayConfs[a.id]?.nickname || a.name}
                    {!displayConfs[a.id]?.nickname && (
                      <button onClick={() => setEditingId(a.id)} className="text-muted-foreground hover:text-foreground">
                        <Pencil className="size-3" />
                      </button>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">{a.scene}</p>
                </div>
                <Badge variant={a.status === "running" ? "default" : "secondary"}>
                  {a.status === "running" ? "Online" : a.status === "error" ? "Error" : "Offline"}
                </Badge>
              </div>
              {editingId === a.id && (
                <div className="px-3 pb-2">
                  <div className="flex gap-1 items-center">
                    <input autoFocus className="h-7 text-sm border rounded px-1 flex-1" placeholder="Set nickname..."
                      value={nicknameInput} onChange={e => setNicknameInput(e.target.value)}
                      onKeyDown={async e => {
                        if (e.key === "Enter" && nicknameInput.trim()) {
                          try {
                            await agentsApi.updateDisplay(a.id, { nickname: nicknameInput.trim() } as any)
                            setDisplayConfs(p => ({ ...p, [a.id]: { nickname: nicknameInput.trim() } }))
                          } catch {}
                          setEditingId(null)
                          setNicknameInput("")
                        }
                        if (e.key === "Escape") {
                          setEditingId(null)
                          setNicknameInput("")
                        }
                      }} />
                  </div>
                </div>
              )}
            </Fragment>
          ))}
        </div>
      )}
    </div>
  )
}
