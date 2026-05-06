import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { useT } from "@/context/LanguageContext"
import { scenesApi } from "@/api/scenes"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Plus } from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"

export default function Scenes() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const [createOpen, setCreateOpen] = useState(false)
  const [newSceneId, setNewSceneId] = useState("")
  const queryClient = useQueryClient()
  const t = useT()

  if (isLoading) return <CardGridSkeleton count={4} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("page.scenes")}</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> {t("scene.create")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("scene_dialog.title")}</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">{t("scene_dialog.id")}</label>
                <Input value={newSceneId} onChange={e => setNewSceneId(e.target.value)}
                  placeholder={t("scene_dialog.id_placeholder")} />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
                <Button size="sm" disabled={!newSceneId.trim()} onClick={async () => {
                  await scenesApi.create(newSceneId.trim())
                  queryClient.invalidateQueries({ queryKey: ["scenes"] })
                  setCreateOpen(false)
                  setNewSceneId("")
                }}>{t("common.create")}</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {!data?.scenes?.length ? (
        <p className="text-muted-foreground">{t("scene.no_scenes")}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.scenes.map(s => (
            <Link key={s.id} to={`/scenes/${s.id}`}>
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
                <CardHeader>
                  <CardTitle>{s.id}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-2">
                  <p className="line-clamp-2">{s.context}</p>
                  <div className="flex flex-wrap gap-1">
                    {s.env_skills.map(sk => (
                      <Badge key={sk} variant="outline">{sk}</Badge>
                    ))}
                  </div>
                  <div className="text-xs">
                    {`${t("common.knowledge")}: ${s.mounted_kbs.length} | ${t("common.agents")}: ${s.roster.length}`}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
