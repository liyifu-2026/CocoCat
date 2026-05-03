import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { scenesApi } from "@/api/scenes"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Plus } from "lucide-react"

export default function Scenes() {
  const { data, isLoading } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const [createOpen, setCreateOpen] = useState(false)
  const [newSceneId, setNewSceneId] = useState("")
  const queryClient = useQueryClient()

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scenes</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> Create Scene</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>New Scene</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Scene ID</label>
                <Input value={newSceneId} onChange={e => setNewSceneId(e.target.value)}
                  placeholder="e.g. marketing" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button>
                <Button size="sm" disabled={!newSceneId.trim()} onClick={async () => {
                  await scenesApi.create(newSceneId.trim())
                  queryClient.invalidateQueries({ queryKey: ["scenes"] })
                  setCreateOpen(false)
                  setNewSceneId("")
                }}>Create</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {isLoading && <p className="text-muted-foreground">Loading...</p>}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.scenes?.map(s => (
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
                  KBs: {s.mounted_kbs.length} | Agents: {s.roster.length}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
