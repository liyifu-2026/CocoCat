import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { scenesApi } from "@/api/scenes"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function Scenes() {
  const { data, isLoading } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Scenes</h1>
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
