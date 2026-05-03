import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

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

  const agent = agentsData?.agents?.find(a => a.id === id)
  if (!agent) return <div className="p-6 text-muted-foreground">Agent not found</div>

  return (
    <div className="p-6 space-y-6">
      <Link
        to="/agents"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to Agents
      </Link>
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{agent.name}</h1>
        <Badge variant={agent.enabled ? "default" : "secondary"}>
          {agent.enabled ? "Online" : "Offline"}
        </Badge>
      </div>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
          <TabsTrigger value="memory">Memory</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-4">
          {profile.isLoading ? (
            <TabSkeleton />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Profile</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <strong>ID:</strong> {agent.id}
                </div>
                <div>
                  <strong>Name:</strong> {agent.name}
                </div>
                <div>
                  <strong>Scene:</strong> {agent.scene}
                </div>
                {profile.data && (
                  <>
                    <div>
                      <strong>Role:</strong> {profile.data.role}
                    </div>
                    <div>
                      <strong>Objective:</strong> {profile.data.objective}
                    </div>
                    <div>
                      <strong>Traits:</strong>
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
                        <strong>Rules:</strong>
                        <ul className="list-disc list-inside mt-1 text-muted-foreground">
                          {profile.data.rules.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {profile.data.background && (
                      <div>
                        <strong>Background:</strong>
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
          {skills.isLoading ? (
            <TabSkeleton />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Public Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  {skills.data?.public?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {skills.data.public.map(s => (
                        <Badge key={s}>{s}</Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">None</p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Private Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  {skills.data?.private?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {skills.data.private.map(s => (
                        <Badge key={s} variant="secondary">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">None</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="memory" className="mt-4">
          {memory.isLoading ? (
            <TabSkeleton />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Memory</CardTitle>
              </CardHeader>
              <CardContent className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {memory.data?.content || "(No memories yet)"}
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
                <CardTitle>History</CardTitle>
              </CardHeader>
              <CardContent>
                {history.data?.entries?.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Time</TableHead>
                        <TableHead>Prompt</TableHead>
                        <TableHead>Response</TableHead>
                        <TableHead>Iters</TableHead>
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
                  <p className="text-sm text-muted-foreground">No history yet</p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
