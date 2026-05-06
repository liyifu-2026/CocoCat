import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { entriesApi } from "@/api/entries"
import { EntryManager } from "@/components/EntryManager"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import type { AgentDisplay } from "@/api/agents"
import { AvatarPicker } from "@/components/AvatarPicker"
import { ArrowLeft, Pencil } from "lucide-react"
import { AgentAvatar } from "@/components/AgentAvatar"
import { GENDER_COLORS } from "@/components/avatars"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { useT } from "@/context/LanguageContext"

function TabSkeleton() {
  return (
    <div className="space-y-2 p-4">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

export default function AgentDetail() {
  const t = useT()
  const { id } = useParams<{ id: string }>()
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const profile = useQuery({
    queryKey: ["agent", id, "profile"],
    queryFn: () => agentsApi.profile(id!),
    enabled: !!id,
  })
  const skills = useQuery({
    queryKey: ["agent", id, "skills"],
    queryFn: () => agentsApi.skills(id!),
    enabled: !!id,
  })
  const memory = useQuery({
    queryKey: ["agent", id, "memory"],
    queryFn: () => agentsApi.memory(id!),
    enabled: !!id,
  })
  const history = useQuery({
    queryKey: ["agent", id, "history"],
    queryFn: () => agentsApi.history(id!),
    enabled: !!id,
  })

  const channels = useQuery({ queryKey: ["channels"], queryFn: () => entriesApi.listChannels() })
  const entriesConfig = useQuery({
    queryKey: ["agent", id, "entries"],
    queryFn: () => entriesApi.getAgentEntries(id!),
    enabled: !!id,
  })

  const { data: displayData } = useQuery({
    queryKey: ["agent", id, "display"],
    queryFn: () => agentsApi.display(id!),
    enabled: !!id,
  })

  const [editingSkills, setEditingSkills] = useState(false)
  const [publicSkills, setPublicSkills] = useState<string[]>([])
  const [privateSkills, setPrivateSkills] = useState<string[]>([])
  const [newPublicSkill, setNewPublicSkill] = useState("")
  const [newPrivateSkill, setNewPrivateSkill] = useState("")
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [displayOpen, setDisplayOpen] = useState(false)
  const [displayConfig, setDisplayConfig] = useState<AgentDisplay>({ nickname: "", avatar: "", color: "" })
  const queryClient = useQueryClient()

  const agent = agentsData?.agents?.find(a => a.id === id)
  if (!agent) return <div className="p-6 text-muted-foreground">{t("agent.not_found")}</div>

  return (
    <div className="p-6 space-y-6">
      <Link
        to="/agents"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {t("agent.back_to_list")}
      </Link>
      <div className="flex items-center gap-3">
        <AgentAvatar
          avatarId={displayData?.avatar}
          gender={displayData?.gender}
          color={displayData?.color}
          name={agent.name}
          size="md"
        />
        <div>
          <h1 className="text-2xl font-bold">{displayData?.nickname || agent.name}</h1>
          <p className="text-sm text-muted-foreground">{agent.id}</p>
        </div>
        <Badge variant={agent.status === "running" ? "default" : "secondary"}>
          {agent.status === "running" ? t("common.online") : agent.status === "error" ? t("common.error_status") : t("common.offline")}
        </Badge>
        {id === "leader" && (
          <Badge variant="outline" className="ml-2">Leader</Badge>
        )}
      </div>
      {id !== "leader" && (
        <div className="flex items-center gap-4">
          <Button
            variant={agent.status === "running" ? "secondary" : "default"}
            size="sm"
            onClick={async () => {
              const newStatus = agent.status === "running" ? "stopped" : "running"
              await agentsApi.update(agent.id, { status: newStatus })
              queryClient.invalidateQueries({ queryKey: ["agents"] })
            }}
          >
            {agent.status === "running" ? t("agent.disable") : t("agent.enable")}
          </Button>
          <Button size="sm" variant="outline" onClick={() => {
            setDisplayConfig(displayData ?? { nickname: "", avatar: "", color: "" })
            setDisplayOpen(true)
          }}>
            <Pencil className="size-3 mr-1" /> {t("agent.edit_display")}
          </Button>
        </div>
      )}

      <Dialog open={displayOpen} onOpenChange={setDisplayOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>{t("agent.customize_display")}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1 block">{t("agent.nickname")}</label>
              <Input value={displayConfig.nickname} onChange={e => setDisplayConfig(p => ({ ...p, nickname: e.target.value }))}
                placeholder={agent.name} />
            </div>
            <AvatarPicker
              currentAvatar={displayConfig.avatar}
              currentColor={displayConfig.color}
              gender={displayConfig.gender}
              onAvatarChange={a => setDisplayConfig(p => ({ ...p, avatar: a }))}
              onColorChange={c => setDisplayConfig(p => ({ ...p, color: c }))}
            />
            <div className="flex items-center gap-3 pt-2">
              <div className="text-sm text-muted-foreground">{t("agent.preview")}</div>
              <div className="flex items-center gap-2">
                <AgentAvatar avatarId={displayConfig.avatar} color={displayConfig.color}
                  gender={displayConfig.gender} name={agent.name} size="md" />
                <span className="text-sm font-medium">{displayConfig.nickname || agent.name}</span>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setDisplayOpen(false)}>{t("common.cancel")}</Button>
              <Button size="sm" onClick={async () => {
                await agentsApi.updateDisplay(agent.id, displayConfig)
                queryClient.invalidateQueries({ queryKey: ["agent", id, "display"] })
                setDisplayOpen(false)
              }}>{t("common.save")}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">{t("agent.profile")}</TabsTrigger>
          <TabsTrigger value="skills">{t("agent.skills")}</TabsTrigger>
          <TabsTrigger value="memory">{t("agent.memory")}</TabsTrigger>
          <TabsTrigger value="history">{t("agent.history")}</TabsTrigger>
          <TabsTrigger value="entries">{t("agent.entries")}</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-4">
          {profile.isLoading ? (
            <TabSkeleton />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t("agent.profile")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <strong>{t("agent.id")}</strong> {agent.id}
                </div>
                <div>
                  <strong>{t("agent.name")}</strong> {agent.name}
                </div>
                <div>
                  <strong>{t("agent.scene")}</strong> {agent.scene}
                </div>
                {profile.data && (
                  <>
                    <div>
                      <strong>{t("agent.role")}</strong> {profile.data.role}
                    </div>
                    <div>
                      <strong>{t("agent.objective")}</strong> {profile.data.objective}
                    </div>
                    <div>
                      <strong>{t("agent.traits")}</strong>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {profile.data.traits.map((t, i) => (
                          <Badge key={i} variant="outline">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    {profile.data.rules.length > 0 && (
                      <div>
                        <strong>{t("agent.rules")}</strong>
                        <ul className="list-disc list-inside mt-1 text-muted-foreground">
                          {profile.data.rules.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {profile.data.background && (
                      <div>
                        <strong>{t("agent.background")}</strong>
                        <p className="text-muted-foreground mt-1">{profile.data.background}</p>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="skills" className="mt-4">
          {skills.isLoading ? <TabSkeleton /> : (
            <div className="space-y-4">
              <div className="flex justify-end">
                {editingSkills ? (
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setEditingSkills(false)}>{t("common.cancel")}</Button>
                    <Button size="sm" onClick={async () => {
                      await agentsApi.updateSkills(agent.id, { public: publicSkills, private: privateSkills })
                      queryClient.invalidateQueries({ queryKey: ["agent", id, "skills"] })
                      setEditingSkills(false)
                    }}>{t("common.save")}</Button>
                  </div>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => {
                    setPublicSkills(skills.data?.public ?? [])
                    setPrivateSkills(skills.data?.private ?? [])
                    setEditingSkills(true)
                  }}>{t("common.edit")}</Button>
                )}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle>{t("agent.public_skills")}</CardTitle></CardHeader>
                  <CardContent>
                    {editingSkills ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          {publicSkills.map((s, i) => (
                            <span key={i} className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-sm">
                              {s}
                              <button onClick={() => setPublicSkills(prev => prev.filter((_, j) => j !== i))}
                                className="text-destructive hover:text-destructive/80">×</button>
                            </span>
                          ))}
                        </div>
                        <div className="flex gap-2">
                          <Input size={1} placeholder={t("agent.add_skill")}
                            value={newPublicSkill} onChange={e => setNewPublicSkill(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === "Enter" && newPublicSkill.trim()) {
                                setPublicSkills(prev => [...prev, newPublicSkill.trim()])
                                setNewPublicSkill("")
                              }
                            }} />
                          <Button size="sm" onClick={() => {
                            if (newPublicSkill.trim()) {
                              setPublicSkills(prev => [...prev, newPublicSkill.trim()])
                              setNewPublicSkill("")
                            }
                          }}>+</Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {skills.data?.public?.map(s => <Badge key={s}>{s}</Badge>)}
                        {(!skills.data?.public?.length) && <p className="text-sm text-muted-foreground">{t("agent.none")}</p>}
                      </div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle>{t("agent.private_skills")}</CardTitle></CardHeader>
                  <CardContent>
                    {editingSkills ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          {privateSkills.map((s, i) => (
                            <span key={i} className="inline-flex items-center gap-1 rounded-md bg-secondary/20 px-2 py-1 text-sm">
                              {s}
                              <button onClick={() => setPrivateSkills(prev => prev.filter((_, j) => j !== i))}
                                className="text-destructive hover:text-destructive/80">×</button>
                            </span>
                          ))}
                        </div>
                        <div className="flex gap-2">
                          <Input size={1} placeholder={t("agent.add_skill")}
                            value={newPrivateSkill} onChange={e => setNewPrivateSkill(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === "Enter" && newPrivateSkill.trim()) {
                                setPrivateSkills(prev => [...prev, newPrivateSkill.trim()])
                                setNewPrivateSkill("")
                              }
                            }} />
                          <Button size="sm" onClick={() => {
                            if (newPrivateSkill.trim()) {
                              setPrivateSkills(prev => [...prev, newPrivateSkill.trim()])
                              setNewPrivateSkill("")
                            }
                          }}>+</Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {skills.data?.private?.map(s => <Badge key={s} variant="secondary">{s}</Badge>)}
                        {(!skills.data?.private?.length) && <p className="text-sm text-muted-foreground">{t("agent.none")}</p>}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="memory" className="mt-4">
          {memory.isLoading ? (
            <TabSkeleton />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t("agent.memory")}</CardTitle>
              </CardHeader>
              <CardContent className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {memory.data?.content || t("agent.no_memories")}
                </ReactMarkdown>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          {history.isLoading ? (
            <TabSkeleton />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t("agent.history")}</CardTitle>
              </CardHeader>
              <CardContent>
                {history.data?.entries?.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("agent.history_time")}</TableHead>
                        <TableHead>{t("agent.history_prompt")}</TableHead>
                        <TableHead>{t("agent.history_response")}</TableHead>
                        <TableHead>{t("agent.history_iters")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {history.data.entries
                        .slice()
                        .reverse()
                        .map((e, i) => (
                          <TableRow key={i}>
                            <TableCell className="text-xs whitespace-nowrap">
                              {e.timestamp?.slice(0, 19).replace("T", " ")}
                            </TableCell>
                            <TableCell className="text-xs max-w-[200px] truncate">
                              {e.prompt}
                            </TableCell>
                            <TableCell className="text-xs max-w-[200px] truncate">
                              {e.response_summary}
                            </TableCell>
                            <TableCell className="text-xs">{e.iterations}</TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-sm text-muted-foreground">{t("agent.no_history")}</p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="entries" className="mt-4">
          <EntryManager
            title={t("agent.personal_entries")}
            entries={entriesConfig.data?.entries}
            allChannels={channels.data?.channels}
            onSave={async (newEntries) => {
              await entriesApi.updateAgentEntries(agent.id, newEntries)
              queryClient.invalidateQueries({ queryKey: ["agent", id, "entries"] })
            }}
          />
          <p className="text-xs text-muted-foreground mt-2">
            {t("agent.entries_desc")}
          </p>
        </TabsContent>
      </Tabs>
      {id !== "leader" && (
        <div className="pt-4 border-t border-border">
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive" size="sm">{t("agent.delete")}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{t("agent.delete_confirm").replace("{name}", agent.name)}</DialogTitle></DialogHeader>
              <p className="text-sm text-muted-foreground">{t("agent.delete_desc")}</p>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" size="sm" onClick={() => setDeleteDialogOpen(false)}>{t("common.cancel")}</Button>
                <Button variant="destructive" size="sm" onClick={async () => {
                  await agentsApi.delete(agent.id)
                  queryClient.invalidateQueries({ queryKey: ["agents"] })
                  setDeleteDialogOpen(false)
                  window.location.href = "/agents"
                }}>{t("common.delete")}</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </div>
  )
}
