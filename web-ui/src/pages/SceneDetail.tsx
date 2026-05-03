import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { scenesApi } from "@/api/scenes"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"

export default function SceneDetail() {
  const { id } = useParams<{ id: string }>()
  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const scene = data?.scenes?.find(s => s.id === id)

  if (!scene) return <div className="p-6 text-muted-foreground">Scene not found</div>

  return (
    <div className="p-6 space-y-6">
      <Link to="/scenes" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to Scenes
      </Link>
      <h1 className="text-2xl font-bold">{scene.id}</h1>

      <Card>
        <CardHeader><CardTitle>Context</CardTitle></CardHeader>
        <CardContent>
          <pre className="whitespace-pre-wrap text-sm">{scene.context}</pre>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Knowledge Bases</CardTitle></CardHeader>
          <CardContent>
            {scene.mounted_kbs.length === 0 ? (
              <p className="text-sm text-muted-foreground">None mounted</p>
            ) : (
              <ul className="text-sm space-y-1">
                {scene.mounted_kbs.map(kb => (
                  <li key={kb} className="list-disc list-inside">{kb}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Environment Skills</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-1">
            {scene.env_skills.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              scene.env_skills.map(sk => <Badge key={sk} variant="outline">{sk}</Badge>)
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Roster</CardTitle></CardHeader>
          <CardContent>
            {scene.roster.length === 0 ? (
              <p className="text-sm text-muted-foreground">No agents</p>
            ) : (
              <ul className="text-sm space-y-1">
                {scene.roster.map(a => (
                  <li key={a} className="list-disc list-inside">{a}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
