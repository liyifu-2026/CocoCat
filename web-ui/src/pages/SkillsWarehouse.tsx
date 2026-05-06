import { useQuery, useQueryClient } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Package, Trash2 } from "lucide-react"
import { useT } from "@/context/LanguageContext"

export default function SkillsWarehouse() {
  const t = useT()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["warehouse"],
    queryFn: () => agentsApi.warehouseList(),
    refetchInterval: 30000,
  })

  const { data: caps } = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => agentsApi.capabilities(),
  })

  const skills = data?.skills ?? []
  const agentSkills = caps?.agents ?? []

  function agentCountForSkill(skillId: string) {
    return agentSkills.filter((a: any) => a.skills?.some((s: any) => s.id === skillId)).length
  }

  async function removeSkill(id: string) {
    await agentsApi.delete(id)
    queryClient.invalidateQueries({ queryKey: ["warehouse"] })
    queryClient.invalidateQueries({ queryKey: ["capabilities"] })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("nav.skills")}</h1>
        <Button size="sm" variant="outline" disabled>
          <Package className="size-3 mr-1" /> Install Skill
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1,2,3].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
      ) : skills.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">No skills in warehouse</CardContent></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {skills.map((s: any) => (
            <Card key={s.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{s.name}</CardTitle>
                  <Badge variant="outline" className="text-[10px]">{s.source}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{s.description || s.id}</p>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{agentCountForSkill(s.id)} agents</span>
                  <button onClick={() => removeSkill(s.id)} className="text-destructive hover:text-destructive/80">
                    <Trash2 className="size-3" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
