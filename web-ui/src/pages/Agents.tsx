import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AgentAvatar } from "@/components/AgentAvatar"
import ErrorState from "@/components/ErrorState"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"

export default function Agents() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })

  if (isLoading) return <CardGridSkeleton count={6} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Agents</h1>
      {!data?.agents?.length ? (
        <p className="text-muted-foreground">No agents found.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.agents.map(a => (
            <Link key={a.id} to={`/agents/${a.id}`}>
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AgentAvatar name={a.name} size="sm" />
                    <span>{a.name}</span>
                    <div className="ml-auto">
                      <Badge variant={a.enabled ? "default" : "secondary"}>
                        {a.enabled ? "Online" : "Offline"}
                      </Badge>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-1">
                  <div>ID: {a.id}</div>
                  <div>Scene: {a.scene}</div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
