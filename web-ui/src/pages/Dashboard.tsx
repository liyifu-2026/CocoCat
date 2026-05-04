import { useQuery } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import { scenesApi } from "@/api/scenes"
import { hiringApi } from "@/api/hiring"
import { chatApi } from "@/api/chat"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Users, FolderKanban, UserPlus, MessageSquare } from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { Skeleton } from "@/components/ui/skeleton"

export default function Dashboard() {
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const scenes = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const hires = useQuery({ queryKey: ["hiring"], queryFn: () => hiringApi.listPending() })
  const chatGroups = useQuery({ queryKey: ["chat-groups"], queryFn: () => chatApi.listGroups() })
  const defaultGroup = chatGroups.data?.groups?.find(g => g.is_default) ?? chatGroups.data?.groups?.[0]
  const chatMessages = useQuery({
    queryKey: ["chat-messages", defaultGroup?.id],
    queryFn: () => chatApi.getMessages(defaultGroup!.id, 10),
    enabled: !!defaultGroup,
  })

  const onlineAgents = agents.data?.agents?.filter(a => a.enabled).length ?? 0
  const sceneCount = scenes.data?.scenes?.length ?? 0
  const pendingHires = hires.data?.pending?.length ?? 0
  const recentMessages = chatMessages.data?.messages?.length ?? 0

  const isAnyError = agents.isError || scenes.isError || hires.isError || chatMessages.isError

  const metrics = [
    { label: "Online Agents", value: onlineAgents, icon: Users, loading: agents.isLoading },
    { label: "Scenes", value: sceneCount, icon: FolderKanban, loading: scenes.isLoading },
    { label: "Pending Hires", value: pendingHires, icon: UserPlus, loading: hires.isLoading },
    { label: "Recent Messages", value: recentMessages, icon: MessageSquare, loading: chatMessages.isLoading },
  ]

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      {isAnyError && (
        <ErrorState
          message={agents.error?.message ?? scenes.error?.message ?? hires.error?.message ?? chatMessages.error?.message}
          onRetry={() => { agents.refetch(); scenes.refetch(); hires.refetch(); chatMessages.refetch() }}
        />
      )}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {metrics.map(m => (
          <Card key={m.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{m.label}</CardTitle>
              <m.icon className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {m.loading ? <Skeleton className="h-8 w-16" /> : m.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-lg">Agents</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {agents.data?.agents?.map(a => (
              <div key={a.id} className="flex items-center justify-between">
                <span className="font-medium">{a.name}</span>
                <Badge variant={a.enabled ? "default" : "secondary"}>
                  {a.enabled ? "Online" : "Disabled"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-lg">Recent Chat</CardTitle></CardHeader>
          <CardContent className="space-y-2 max-h-64 overflow-auto">
            {chatMessages.data?.messages?.slice(-5).reverse().map((m, i) => (
              <div key={i} className="text-sm border-b border-border pb-1">
                <span className="font-medium">[{m.from}]</span> {m.content.substring(0, 120)}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
