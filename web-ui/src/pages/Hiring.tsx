import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { hiringApi } from "@/api/hiring"
import { agentsApi } from "@/api/agents"
import type { PendingHire } from "@/api/hiring"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import {
  UserPlus, Check, X, Clock, Sparkles, Send, Users,
} from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { useT } from "@/context/LanguageContext"

export default function Hiring() {
  const t = useT()
  const queryClient = useQueryClient()
  const [position, setPosition] = useState("")
  const [skills, setSkills] = useState("")
  const [responsibilities, setResponsibilities] = useState("")
  const [traits, setTraits] = useState("")
  const [count, setCount] = useState(5)
  const [submitting, setSubmitting] = useState(false)
  const [acceptingId, setAcceptingId] = useState<string | null>(null)
  const [nickname, setNickname] = useState("")

  const { data: pending, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["hiring"],
    queryFn: () => hiringApi.listPending(),
    refetchInterval: 5000,
  })

  if (isLoading) return <CardGridSkeleton count={3} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  async function submitPlan() {
    if (!position.trim()) return
    setSubmitting(true)
    try {
      await hiringApi.createPlan({
        position: position.trim(),
        skills,
        responsibilities,
        traits,
        count,
      })
      toast.success("Hiring plan submitted to Leader")
      setPosition(""); setSkills(""); setResponsibilities(""); setTraits("")
    } catch {
      toast.error("Failed to submit plan")
    } finally {
      setSubmitting(false)
    }
  }

  async function confirmApprove(hire: PendingHire) {
    try {
      await hiringApi.approve(hire.id)
      if (nickname.trim()) {
        try {
          await agentsApi.updateDisplay(hire.id, { nickname: nickname.trim() } as any)
        } catch {}
      }
      toast.success(t("hiring.approved"))
      queryClient.invalidateQueries({ queryKey: ["hiring"] })
      queryClient.invalidateQueries({ queryKey: ["agents"] })
    } catch { toast.error("Failed to approve") }
    finally { setAcceptingId(null); setNickname("") }
  }

  async function rejectHire(hire: PendingHire) {
    try {
      await hiringApi.reject(hire.id)
      toast.success(t("hiring.rejected"))
      queryClient.invalidateQueries({ queryKey: ["hiring"] })
    } catch { toast.error("Failed to reject") }
  }

  const hires = pending?.pending ?? []

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="stagger-item flex items-center gap-3" style={{animationDelay: "0s"}}>
        <h1 className="text-2xl font-bold">{t("hiring.title")}</h1>
        <Badge variant="outline" className="gap-1">
          <Clock className="size-3" /> {t("hiring.pending_count").replace("{count}", String(hires.length))}
        </Badge>
      </div>

      {/* Hiring Plan Form */}
      <Card className="stagger-item" style={{animationDelay: "0.08s"}}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="size-4" />
            Post a Hiring Plan
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Position</Label>
              <Input value={position} onChange={e => setPosition(e.target.value)}
                placeholder="e.g. Customer Support Specialist" />
            </div>
            <div className="space-y-2">
              <Label>Number of Candidates</Label>
              <Input type="number" min={1} max={10} value={count}
                onChange={e => setCount(parseInt(e.target.value) || 5)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Required Skills</Label>
            <Input value={skills} onChange={e => setSkills(e.target.value)}
              placeholder="e.g. patience, communication, problem-solving" />
          </div>
          <div className="space-y-2">
            <Label>Responsibilities</Label>
            <Textarea value={responsibilities} onChange={e => setResponsibilities(e.target.value)}
              placeholder="Describe the role's responsibilities..." className="min-h-[80px]" />
          </div>
          <div className="space-y-2">
            <Label>Desired Traits</Label>
            <Input value={traits} onChange={e => setTraits(e.target.value)}
              placeholder="e.g. detail-oriented, responsible" />
          </div>
          <Button onClick={submitPlan} disabled={!position.trim() || submitting} className="gap-2">
            <Send className="size-4" />
            {submitting ? "Submitting..." : "Let Leader Dream Up Candidates"}
          </Button>
        </CardContent>
      </Card>

      {/* Candidate Cards */}
      {hires.length > 0 && (
        <div className="stagger-item" style={{animationDelay: "0.16s"}}>
          <div className="flex items-center gap-2 mb-4">
            <Users className="size-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Pending Approval ({hires.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {hires.map(hire => (
              <Card key={hire.id}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold">{hire.name}</h4>
                      <p className="text-xs text-muted-foreground">{hire.profile?.role || "N/A"}</p>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">{hire.id}</Badge>
                  </div>
                  {hire.profile?.objective && (
                    <p className="text-sm text-muted-foreground">{hire.profile.objective}</p>
                  )}
                  {hire.profile?.traits?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {hire.profile.traits.map((trait: string, i: number) => (
                        <Badge key={i} variant="outline" className="text-[10px]">{trait}</Badge>
                      ))}
                    </div>
                  )}
                  {hire.profile?.background && (
                    <p className="text-xs text-muted-foreground">{hire.profile.background}</p>
                  )}
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" className="flex-1" onClick={() => setAcceptingId(hire.id)}>
                      <Check className="size-3 mr-1" /> {t("hiring.approve")}
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => rejectHire(hire)}>
                      <X className="size-3 mr-1" /> {t("hiring.reject")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {hires.length === 0 && (
        <div className="stagger-item text-center py-16 text-muted-foreground" style={{animationDelay: "0.16s"}}>
          <UserPlus className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("hiring.no_pending")}</p>
          <p className="text-sm mt-1">{t("hiring.no_pending_desc")}</p>
        </div>
      )}

      {/* Nickname Dialog */}
      <Dialog open={!!acceptingId} onOpenChange={(o) => { if (!o) { setAcceptingId(null); setNickname("") } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Set Nickname</DialogTitle>
            <DialogDescription>
              Give this new team member a nickname. Leave empty to use their original name.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nickname</Label>
              <Input value={nickname} onChange={e => setNickname(e.target.value)}
                placeholder="Optional nickname..." autoFocus
                onKeyDown={e => {
                  if (e.key === "Enter") {
                    const hire = hires.find(h => h.id === acceptingId)
                    if (hire) confirmApprove(hire)
                  }
                }} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => {
                const hire = hires.find(h => h.id === acceptingId)
                if (hire) confirmApprove(hire)
              }}>Skip</Button>
              <Button size="sm" onClick={() => {
                const hire = hires.find(h => h.id === acceptingId)
                if (hire) confirmApprove(hire)
              }}>Confirm</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
