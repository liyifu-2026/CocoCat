import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { knowledgeApi } from "@/api/knowledge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen } from "lucide-react"

export default function Knowledge() {
  const { data, isLoading } = useQuery({ queryKey: ["knowledge"], queryFn: () => knowledgeApi.list() })

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Knowledge Bases</h1>
      {isLoading && <p className="text-muted-foreground">Loading...</p>}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.kbs?.map(kb => (
          <Link key={kb.id} to={`/knowledge/${kb.id}`}>
            <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="size-4" /> {kb.id}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Click to browse wiki pages
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
