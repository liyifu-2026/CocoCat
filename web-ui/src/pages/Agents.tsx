import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Crown, Users, Pencil } from "lucide-react"
import { agentsApi } from "@/api/agents"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { AgentAvatar } from "@/components/AgentAvatar"
import ErrorState from "@/components/ErrorState"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import { useT } from "@/context/LanguageContext"

export default function Agents() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [nicknameInput, setNicknameInput] = useState("")
  const [displayConfs, setDisplayConfs] = useState<Record<string, {nickname?: string}>>({})
  const t = useT()

  useEffect(() => {
    const list = Array.isArray(data) ? data : data?.agents ?? []
    if (!list.length) return
    list.forEach(async (a: any) => {
      try {
        const d = await agentsApi.display(a.id)
        if (d?.nickname) setDisplayConfs(p => ({ ...p, [a.id]: { nickname: d.nickname } }))
      } catch {}
    })
  }, [data])

  if (isLoading) return <CardGridSkeleton count={6} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  const agents: any[] = Array.isArray(data) ? data : data?.agents ?? []
  const leader = agents.find((a: any) => a.id === "leader")
  const members = agents.filter((a: any) => a.id !== "leader")

  return (
    <div className="p-6 space-y-6">
      {/* Leader Card */}
      {leader && (
        <div className="stagger-item rounded-lg border border-l-4 border-l-primary bg-muted/30 p-6" style={{animationDelay: "0s"}}>
          <div className="flex items-start gap-5">
            <AgentAvatar name={displayConfs["leader"]?.nickname || leader.name} size="lg"
              status={leader.status === "running" ? "idle" : leader.status === "error" ? "busy" : undefined} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Crown className="size-5 text-yellow-500 shrink-0" />
                <h2 className="text-xl font-bold truncate">{displayConfs["leader"]?.nickname || leader.name}</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                {leader.role} &middot; {leader.scene}
              </p>
              <div className="flex items-center gap-2 mt-3">
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/agents/${leader.id}`}>{t("agent.edit_display")}</Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link to={`/agents/${leader.id}`}>{t("common.edit")}</Link>
                </Button>
              </div>
            </div>
            <Badge variant={leader.status === "running" ? "default" : "secondary"} className="shrink-0">
              {leader.status === "running" ? t("common.online") : leader.status === "error" ? t("common.error_status") : t("common.offline")}
            </Badge>
          </div>
        </div>
      )}

      {/* Team Members */}
      {members.length > 0 && (
        <div className="stagger-item" style={{animationDelay: "0.08s"}}>
          <div className="flex items-center gap-2 mb-4">
            <Users className="size-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              {t("common.members")} ({members.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {members.map((a: any) => (
              <Card key={a.id}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Link to={`/agents/${a.id}`}>
                      <AgentAvatar name={displayConfs[a.id]?.nickname || a.name} size="md"
                        status={a.status === "running" ? "idle" : a.status === "error" ? "busy" : undefined} />
                    </Link>
                    <div className="flex-1 min-w-0">
                      <Link to={`/agents/${a.id}`} className="font-medium hover:underline truncate block">
                        {displayConfs[a.id]?.nickname || a.name}
                      </Link>
                      <p className="text-xs text-muted-foreground truncate">{a.scene}</p>
                    </div>
                    <Badge variant={a.status === "running" ? "default" : "secondary"} className="shrink-0 text-[10px]">
                      {a.status === "running" ? t("common.online") : a.status === "error" ? t("common.error_status") : t("common.offline")}
                    </Badge>
                  </div>
                  {!displayConfs[a.id]?.nickname && (
                    <button onClick={() => setEditingId(a.id)} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                      <Pencil className="size-3" />
                      {t("agents.set_nickname")}
                    </button>
                  )}
                  {editingId === a.id && (
                    <div className="mt-2">
                      <input autoFocus className="w-full h-7 text-sm border rounded px-1"
                        placeholder={t("agents.set_nickname")}
                        value={nicknameInput}
                        onChange={e => setNicknameInput(e.target.value)}
                        onKeyDown={async e => {
                          if (e.key === "Enter" && nicknameInput.trim()) {
                            try {
                              await agentsApi.updateDisplay(a.id, { nickname: nicknameInput.trim() } as any)
                              setDisplayConfs(p => ({ ...p, [a.id]: { nickname: nicknameInput.trim() } }))
                            } catch {}
                            setEditingId(null)
                            setNicknameInput("")
                          }
                          if (e.key === "Escape") { setEditingId(null); setNicknameInput("") }
                        }} />
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {agents.length === 0 && (
        <p className="stagger-item text-muted-foreground" style={{animationDelay: "0.16s"}}>{t("agents.no_agents")}</p>
      )}
    </div>
  )
}
