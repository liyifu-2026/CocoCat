import { useQuery } from "@tanstack/react-query"
import { agentsApi } from "@/api/agents"
import type { UsageEntry } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { BarChart3, Cpu } from "lucide-react"
import { TableSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { useT } from "@/context/LanguageContext"

export default function TokenUsage() {
  const t = useT()
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["usage"], queryFn: () => agentsApi.usage(100) })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })

  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  const usage = data?.usage ?? []
  const totalTokens = usage.reduce((sum, u) => sum + u.total_tokens, 0)
  const totalIterations = usage.reduce((sum, u) => sum + u.iterations, 0)

  function agentName(agentId: string) {
    return agentsData?.agents?.find(a => a.id === agentId)?.name ?? agentId
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <BarChart3 className="size-6" /> {t("usage.title")}
      </h1>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.total_tokens")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTokens.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.total_iterations")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalIterations.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t("usage.unique_agents")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {new Set(usage.map(u => u.agent_id)).size}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("usage.history")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <TableSkeleton rows={5} cols={6} />}
          {!isLoading && usage.length === 0 && (
            <div className="text-center py-10 text-muted-foreground">
              <Cpu className="size-12 mx-auto mb-4 opacity-30" />
              <p>{t("usage.no_data")}</p>
            </div>
          )}
          {usage.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("usage.agent")}</TableHead>
                  <TableHead>{t("usage.time")}</TableHead>
                  <TableHead>{t("usage.input_tokens")}</TableHead>
                  <TableHead>{t("usage.output_tokens")}</TableHead>
                  <TableHead>{t("usage.total")}</TableHead>
                  <TableHead>{t("usage.iterations")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usage.slice().reverse().map((u, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Badge variant="outline">{agentName(u.agent_id)}</Badge>
                    </TableCell>
                    <TableCell className="text-xs whitespace-nowrap">
                      {u.timestamp?.slice(0, 19).replace("T", " ")}
                    </TableCell>
                    <TableCell>{u.input_tokens?.toLocaleString() ?? "-"}</TableCell>
                    <TableCell>{u.output_tokens?.toLocaleString() ?? "-"}</TableCell>
                    <TableCell className="font-medium">{u.total_tokens?.toLocaleString()}</TableCell>
                    <TableCell>{u.iterations}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
