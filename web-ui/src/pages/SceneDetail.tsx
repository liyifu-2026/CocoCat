import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { scenesApi } from "@/api/scenes"
import { agentsApi } from "@/api/agents"
import { entriesApi } from "@/api/entries"
import { EntryManager } from "@/components/EntryManager"
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
  const t = useT()
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const channels = useQuery({ queryKey: ["channels"], queryFn: () => entriesApi.listChannels() })
  const entriesConfig = useQuery({
    queryKey: ["scene", id, "entries"],
    queryFn: () => entriesApi.getSceneEntries(id!),
    enabled: !!id,
  })
  const [editingContext, setEditingContext] = useState(false)
  const [contextText, setContextText] = useState("")
  const [newKb, setNewKb] = useState("")
  const [newSkill, setNewSkill] = useState("")
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!scene) return <div className="p-6 text-muted-foreground">{t("scene.not_found")}</div>

  return (
    <div className="p-6 space-y-6">
      <Link to="/scenes" className="stagger-item inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground" style={{animationDelay: "0s"}}>
        <ArrowLeft className="size-4" /> {t("scene.back_to_all")}
      </Link>
      <h1 className="stagger-item text-2xl font-bold" style={{animationDelay: "0.08s"}}>{scene.id}</h1>

      <Card className="stagger-item" style={{animationDelay: "0.16s"}}>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t("scene.context")}</CardTitle>
          {editingContext ? (
            <div className="flex gap-2">
              <Button size="xs" variant="outline" onClick={() => setEditingContext(false)}>{t("scene.context_cancel")}</Button>
              <Button size="xs" onClick={async () => {
                await scenesApi.updateContext(scene.id, contextText)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setEditingContext(false)
              }}>{t("scene.context_save")}</Button>
            </div>
          ) : (
            <Button size="xs" variant="outline"
              onClick={() => { setContextText(scene.context); setEditingContext(true) }}>
              <Pencil className="size-3 mr-1" /> {t("scene.context_edit")}
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

      <div className="stagger-item grid gap-4 md:grid-cols-3" style={{animationDelay: "0.24s"}}>
        <Card>
          <CardHeader><CardTitle>{t("scene.knowledge_bases")}</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-1 mb-2">
              {(scene.mounted_kbs ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("scene.no_kbs")}</p>
              ) : (
                (scene.mounted_kbs ?? []).map((kb, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{kb}</span>
                    <button onClick={async () => {
                      const updated = (scene.mounted_kbs ?? []).filter((_, j) => j !== i)
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
              <Input size={1} placeholder={t("scene.add_kb")} value={newKb} onChange={e => setNewKb(e.target.value)} />
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
          <CardHeader><CardTitle>{t("scene.env_skills")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1 mb-2">
              {(scene.env_skills ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("scene.no_skills")}</p>
              ) : (
                (scene.env_skills ?? []).map((sk, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs">
                    {sk}
                    <button onClick={async () => {
                      const updated = (scene.env_skills ?? []).filter((_, j) => j !== i)
                      await scenesApi.updateSkills(scene.id, updated)
                      queryClient.invalidateQueries({ queryKey: ["scenes"] })
                    }} className="text-destructive hover:text-destructive/80">×</button>
                  </span>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <Input size={1} placeholder={t("scene.add_skill")} value={newSkill} onChange={e => setNewSkill(e.target.value)} />
              <Button size="sm" variant="outline" onClick={async () => {
                if (!newSkill.trim()) return
                const updated = [...(scene.env_skills ?? []), newSkill.trim()]
                await scenesApi.updateSkills(scene.id, updated)
                queryClient.invalidateQueries({ queryKey: ["scenes"] })
                setNewSkill("")
              }}><Plus className="size-3" /></Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("scene.roster")}</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-1 mb-2">
              {(scene.roster ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("scene.no_agents")}</p>
              ) : (
                (scene.roster ?? []).map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{a}</span>
                    <button onClick={async () => {
                      const updated = (scene.roster ?? []).filter((_, j) => j !== i)
                      await scenesApi.updateRoster(scene.id, updated)
                      queryClient.invalidateQueries({ queryKey: ["scenes"] })
                    }} className="text-destructive hover:text-destructive/80 text-xs">×</button>
                  </div>
                ))
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {agentsData?.agents?.filter(a => !(scene.roster ?? []).includes(a.id)).map(a => (
                <Button key={a.id} size="xs" variant="outline" onClick={async () => {
                  const updated = [...(scene.roster ?? []), a.id]
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

      <div className="stagger-item" style={{animationDelay: "0.32s"}}>
        <EntryManager
          title={t("scene.entries")}
          targetType="scene"
          targetId={scene.id}
          entries={entriesConfig.data?.entries}
          allChannels={channels.data?.channels}
          onSave={async (newEntries) => {
            await entriesApi.updateSceneEntries(scene.id, newEntries)
            queryClient.invalidateQueries({ queryKey: ["scene", id, "entries"] })
          }}
        />
      </div>
      <p className="stagger-item text-xs text-muted-foreground -mt-2" style={{animationDelay: "0.40s"}}>
        {t("scene.entries_desc")}
      </p>

      <div className="stagger-item pt-4 border-t border-border" style={{animationDelay: "0.48s"}}>
        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive" size="sm"><Trash2 className="size-4 mr-1" /> {t("scene.delete")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("scene.delete")} {scene.id}?</DialogTitle></DialogHeader>
            <p className="text-sm text-muted-foreground">{t("scene.delete_desc")}</p>
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
