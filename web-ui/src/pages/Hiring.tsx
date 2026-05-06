import { useQuery, useQueryClient } from "@tanstack/react-query"
import { hiringApi } from "@/api/hiring"
import type { PendingHire } from "@/api/hiring"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { UserPlus, Check, X, Clock } from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { useT } from "@/context/LanguageContext"

export default function Hiring() {
  const t = useT()
  const queryClient = useQueryClient()

  const { data: pending, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["hiring"],
    queryFn: () => hiringApi.listPending(),
    refetchInterval: 5000,
  })

  if (isLoading) return <CardGridSkeleton count={3} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  async function approve(hire: PendingHire) {
    await hiringApi.approve(hire.id)
    toast.success(t("hiring.approved"))
    queryClient.invalidateQueries({ queryKey: ["hiring"] })
  }

  async function reject(hire: PendingHire) {
    await hiringApi.reject(hire.id)
    toast.success(t("hiring.rejected"))
    queryClient.invalidateQueries({ queryKey: ["hiring"] })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("hiring.title")}</h1>
        <Badge variant="outline" className="gap-1">
          <Clock className="size-3" /> {t("hiring.pending_count").replace("{count}", String(pending?.pending?.length ?? 0))}
        </Badge>
      </div>

      {(!pending?.pending || pending.pending.length === 0) && (
        <div className="text-center py-20 text-muted-foreground">
          <UserPlus className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("hiring.no_pending")}</p>
          <p className="text-sm mt-1">{t("hiring.no_pending_desc")}</p>
        </div>
      )}

      <div className="space-y-4">
        {pending?.pending?.map(hire => (
          <Card key={hire.id}>
            <CardHeader className="flex flex-row items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {hire.name}
                  <Badge variant="secondary" className="text-xs">{hire.id}</Badge>
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  {`${t("common.scene")}: ${hire.scene} | ${t("common.role")}: ${hire.profile?.role || "N/A"}`}
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => approve(hire)}>
                  <Check className="size-4 mr-1" /> {t("hiring.approve")}
                </Button>
                <Button size="sm" variant="outline" onClick={() => reject(hire)}>
                  <X className="size-4 mr-1" /> {t("hiring.reject")}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="text-sm space-y-2">
              {hire.profile?.objective && (
                <div><strong>{t("hiring.objective")}</strong> {hire.profile.objective}</div>
              )}
              {hire.profile?.traits?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <strong className="mr-1">{t("hiring.traits")}</strong>
                  {hire.profile.traits.map((trait, i) => <Badge key={i} variant="outline">{trait}</Badge>)}
                </div>
              )}
              {hire.profile?.rules?.length > 0 && (
                <div>
                  <strong>{t("hiring.rules")}</strong>
                  <ul className="list-disc list-inside text-muted-foreground mt-1">
                    {hire.profile.rules.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
              {hire.profile?.background && (
                <div><strong>{t("hiring.background")}</strong> {hire.profile.background}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
