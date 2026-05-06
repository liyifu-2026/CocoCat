import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { knowledgeApi } from "@/api/knowledge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen } from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { useT } from "@/context/LanguageContext"

export default function Knowledge() {
  const t = useT()
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["knowledge"], queryFn: () => knowledgeApi.list() })

  if (isLoading) return <CardGridSkeleton count={3} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  if (!data?.kbs || data.kbs.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="stagger-item text-2xl font-bold" style={{animationDelay: "0s"}}>{t("knowledge.title")}</h1>
        <div className="stagger-item text-center py-20 text-muted-foreground" style={{animationDelay: "0.08s"}}>
          <BookOpen className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("knowledge.no_kbs")}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="stagger-item text-2xl font-bold" style={{animationDelay: "0s"}}>{t("knowledge.title")}</h1>
      <div className="stagger-item grid gap-4 md:grid-cols-2 lg:grid-cols-3" style={{animationDelay: "0.08s"}}>
        {data.kbs.map(kb => (
          <Link key={kb.id} to={`/knowledge/${kb.id}`}>
            <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="size-4" /> {kb.id}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {t("knowledge.browse")}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
