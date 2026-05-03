import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { scenesApi } from "@/api/scenes"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { ArrowLeft, Plus, Pencil, Trash2 } from "lucide-react"

export default function SceneDetail() {
  const { id } = useParams<{ id: string }>()
  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const scene = data?.scenes?.find(s => s.id === id)
  const queryClient = useQueryClient()
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const [editingContext, setEditingContext] = useState(false)
  const [contextText, setContextText] = useState("")
  const [newKb, setNewKb] = useState("")
  const [newSkill, setNewSkill] = useState("")
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!scene) return <div className="p-6 text-muted-foreground">Scene not found</div>

  return (
    <div className="p-6 space-y-6">
      <Link to="/scenes" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to Scenes
      </Link>
      <h1 className="text-2xl font-bold">{scene.id}</h1>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Context</CardTitle>
          {editingContext ? (
            <div className="flex gap-2">
              <Button size="xs" variant="outline" onClick={() => setEditingContext(false)}>Cancel</Button>
              <Button size="xs" onClick={async () => {
                await scenesApi.updateContext(scene.id, contextText)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setEditingContext(false)
              }}>Save</Button>
            </div>
          ) : (
            <Button size="xs" variant="outline"
              onClick={() => { setContextText(scene.context); setEditingContext(true) }}>
              <Pencil className="size-3 mr-1" /> Edit
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {editingContext ? (
            <Textarea value={contextText} onChange={e => setContextText(e.target.value)}
              className="min-h-[200px]" />
          ) : (
            <pre className="whitespace-pre-wrap text-sm">{scene.context}</pre>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Knowledge Bases</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-1 mb-2">
              {(scene.mounted_kbs ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">None mounted</p>
              ) : (
                scene.mounted_kbs.map((kb, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{kb}</span>
                    <button onClick={async () => {
                      const updated = scene.mounted_kbs.filter((_, j) => j !== i)
                      const res = await scenesApi.updateKbs(scene.id, updated)
                      queryClient.setQueryData(["scenes"], (old: any) => {
                        if (!old) return old
                        return { scenes: old.scenes.map((s: any) => s.id === scene.id ? { ...s, mounted_kbs: res.mounted } : s) }
                      })
                    }} className="text-destructive hover:text-destructive/80 text-xs">×</button>
                  </div>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <Input size={1} placeholder="KB name..." value={newKb} onChange={e => setNewKb(e.target.value)} />
              <Button size="sm" variant="outline" onClick={async () => {
                if (!newKb.trim()) return
                const updated = [...(scene.mounted_kbs ?? []), newKb.trim()]
                await scenesApi.updateKbs(scene.id, updated)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setNewKb("")
              }}><Plus className="size-3" /></Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Environment Skills</CardTitle></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1 mb-2">
              {scene.env_skills.length === 0 ? (
                <p className="text-sm text-muted-foreground">None</p>
              ) : (
                scene.env_skills.map((sk, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs">
                    {sk}
                    <button onClick={async () => {
                      const updated = scene.env_skills.filter((_, j) => j !== i)
                      await scenesApi.updateSkills(scene.id, updated)
                      queryClient.invalidateQueries({ queryKey: ["scenes"] })
                    }} className="text-destructive hover:text-destructive/80">×</button>
                  </span>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <Input size={1} placeholder="Skill name..." value={newSkill} onChange={e => setNewSkill(e.target.value)} />
              <Button size="sm" variant="outline" onClick={async () => {
                if (!newSkill.trim()) return
                const updated = [...scene.env_skills, newSkill.trim()]
                await scenesApi.updateSkills(scene.id, updated)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setNewSkill("")
              }}><Plus className="size-3" /></Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Roster</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-1 mb-2">
              {scene.roster.length === 0 ? (
                <p className="text-sm text-muted-foreground">No agents</p>
              ) : (
                scene.roster.map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{a}</span>
                    <button onClick={async () => {
                      const updated = scene.roster.filter((_, j) => j !== i)
                      await scenesApi.updateRoster(scene.id, updated)
                      queryClient.invalidateQueries({ queryKey: ["scenes"] })
                    }} className="text-destructive hover:text-destructive/80 text-xs">×</button>
                  </div>
                ))
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {agentsData?.agents?.filter(a => !scene.roster.includes(a.id)).map(a => (
                <Button key={a.id} size="xs" variant="outline" onClick={async () => {
                  const updated = [...scene.roster, a.id]
                  await scenesApi.updateRoster(scene.id, updated)
                  queryClient.invalidateQueries({ queryKey: ["scenes"] })
                }}>
                  <Plus className="size-3 mr-1" /> {a.name}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="pt-4 border-t border-border">
        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive" size="sm"><Trash2 className="size-4 mr-1" /> Delete Scene</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Delete {scene.id}?</DialogTitle></DialogHeader>
            <p className="text-sm text-muted-foreground">This will permanently remove the scene and all its files.</p>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" size="sm" onClick={() => setDeleteOpen(false)}>Cancel</Button>
              <Button variant="destructive" size="sm" onClick={async () => {
                await scenesApi.delete(scene.id)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setDeleteOpen(false)
                window.location.href = "/scenes"
              }}>Delete</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
