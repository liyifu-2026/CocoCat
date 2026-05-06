import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { api } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AgentAvatar } from "@/components/AgentAvatar"
import { Package, Trash2, X, Hash, Users } from "lucide-react"
import { useT } from "@/context/LanguageContext"

export default function SkillsWarehouse() {
  const t = useT()
  const queryClient = useQueryClient()
  const [selectedSkill, setSelectedSkill] = useState<any>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["warehouse"],
    queryFn: () => agentsApi.warehouseList(),
    refetchInterval: 30000,
  })

  const { data: caps } = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => agentsApi.capabilities(),
  })

  const { data: displayData } = useQuery({
    queryKey: ["agent-displays"],
    queryFn: () => agentsApi.listDisplays(),
  })

  const skills = data?.skills ?? []
  const agentSkills = caps?.agents ?? []
  const displays = (displayData as Record<string, { nickname?: string; avatar?: string; color?: string }> | undefined) ?? {}

  function agentsForSkill(skillId: string) {
    return agentSkills.filter((a: any) => a.skills?.some((s: any) => s.id === skillId))
  }

  function agentCountForSkill(skillId: string) {
    return agentsForSkill(skillId).length
  }

  async function removeSkill(id: string) {
    await api.delete(`/skills/warehouse/${id}`)
    queryClient.invalidateQueries({ queryKey: ["warehouse"] })
    queryClient.invalidateQueries({ queryKey: ["capabilities"] })
    setConfirmDelete(null)
    setSelectedSkill(null)
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("nav.skills")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{skills.length} skills · {agentSkills.length} agents</p>
        </div>
        <Button size="sm" variant="outline" disabled>
          <Package className="size-3 mr-1" /> Install Skill
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-28" />)}
        </div>
      ) : skills.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">No skills in warehouse</CardContent></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {skills.map((s: any, i: number) => (
            <button
              key={s.id}
              onClick={() => setSelectedSkill(s)}
              className="stagger-item text-left w-full group"
              style={{animationDelay: `${i * 0.05}s`}}
            >
              <Card className="transition-all duration-200 hover:shadow-md hover:border-primary/30 cursor-pointer h-full">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      {s.name}
                      <Badge variant="outline" className="text-[10px] font-normal opacity-60">{s.source}</Badge>
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{s.description || s.id}</p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Users className="size-3" />
                      <span>{agentCountForSkill(s.id)} agents</span>
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                      onClick={e => { e.stopPropagation(); setConfirmDelete(s.id) }}>
                      <Trash2 className="size-3.5 text-destructive/60 hover:text-destructive" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={!!selectedSkill} onOpenChange={() => { setSelectedSkill(null); setConfirmDelete(null) }}>
        {selectedSkill && (
          <DialogContent className="max-w-lg max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {selectedSkill.name}
                <Badge variant="outline" className="text-[10px]">{selectedSkill.source}</Badge>
              </DialogTitle>
            </DialogHeader>
            <ScrollArea className="max-h-[60vh] pr-2">
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">ID</p>
                  <p className="text-sm font-mono">{selectedSkill.id}</p>
                </div>
                {selectedSkill.description && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Description</p>
                    <p className="text-sm">{selectedSkill.description}</p>
                  </div>
                )}
                {selectedSkill.content && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Content</p>
                    <pre className="text-xs bg-muted rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-[200px]">{selectedSkill.content}</pre>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1.5">
                    <Users className="size-3" /> Assigned to ({agentCountForSkill(selectedSkill.id)} agents)
                  </p>
                  {agentsForSkill(selectedSkill.id).length === 0 ? (
                    <p className="text-xs text-muted-foreground">Not assigned to any agent</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {agentsForSkill(selectedSkill.id).map((a: any) => {
                        const d = displays[a.agent_id] || {}
                        return (
                          <div key={a.agent_id}
                            className="flex items-center gap-2 rounded-full bg-muted px-3 py-1 text-sm">
                            <AgentAvatar name={d.nickname || a.name} avatarId={d.avatar} color={d.color} size="xs" />
                            <span>{d.nickname || a.name}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
                {confirmDelete === selectedSkill.id && (
                  <div className="flex items-center gap-2 pt-2 border-t border-border">
                    <p className="text-xs text-destructive flex-1">Remove this skill from warehouse?</p>
                    <Button size="sm" variant="outline" onClick={() => setConfirmDelete(null)}>
                      <X className="size-3 mr-1" /> Cancel
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => removeSkill(selectedSkill.id)}>
                      <Trash2 className="size-3 mr-1" /> Remove
                    </Button>
                  </div>
                )}
              </div>
            </ScrollArea>
          </DialogContent>
        )}
      </Dialog>
    </div>
  )
}
