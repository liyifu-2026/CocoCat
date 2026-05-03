import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>()
  const { data } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const agent = data?.agents?.find(a => a.id === id)

  if (!agent) return <div className="p-6 text-muted-foreground">Agent not found</div>

  return (
    <div className="p-6 space-y-6">
      <Link to="/agents" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
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
          <Card>
            <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div><strong>ID:</strong> {agent.id}</div>
              <div><strong>Name:</strong> {agent.name}</div>
              <div><strong>Scene:</strong> {agent.scene}</div>
              <div><strong>Status:</strong> {agent.enabled ? "Enabled" : "Disabled"}</div>
              <p className="text-muted-foreground mt-4">
                Profile details and personality data coming from profile.json.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="skills" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Skills</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Skills data coming from skills/manifest.json.
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="memory" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Memory</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              MEMORY.md content coming from memory/MEMORY.md.
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <Card>
            <CardHeader><CardTitle>History</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Task history coming from history.jsonl.
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
