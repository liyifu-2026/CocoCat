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
  FileText, History, UserCheck, UserX, ChevronDown,
  Briefcase, Target, Shield, BookOpen, MapPin,
} from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { useT } from "@/context/LanguageContext"

type Tab = "plan" | "pending" | "history"

export default function Hiring() {
  const t = useT()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>("plan")
  const [position, setPosition] = useState("")
  const [skills, setSkills] = useState("")
  const [responsibilities, setResponsibilities] = useState("")
  const [traits, setTraits] = useState("")
  const [count, setCount] = useState(3)
  const [submitting, setSubmitting] = useState(false)
  const [acceptingId, setAcceptingId] = useState<string | null>(null)
  const [nickname, setNickname] = useState("")

  const { data: pending, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["hiring"],
    queryFn: () => hiringApi.listPending(),
    refetchInterval: 5000,
  })

  const { data: approved } = useQuery({
    queryKey: ["hiring", "approved"],
    queryFn: () => hiringApi.listApproved(),
    enabled: tab === "history",
  })

  const { data: rejected } = useQuery({
    queryKey: ["hiring", "rejected"],
    queryFn: () => hiringApi.listRejected(),
    enabled: tab === "history",
  })

  if (isLoading && tab === "pending") return <CardGridSkeleton count={3} />
  if (isError && tab === "pending") return <ErrorState message={error?.message} onRetry={refetch} />

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
      toast.success("Hiring plan submitted — Leader will dream up candidates")
      setPosition(""); setSkills(""); setResponsibilities(""); setTraits("")
      setTab("pending")
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
  const approvedHires = approved?.approved ?? []
  const rejectedHires = rejected?.rejected ?? []

  const tabs: { id: Tab; label: string; icon: typeof Send }[] = [
    { id: "plan", label: "Post Plan", icon: FileText },
    { id: "pending", label: `Pending (${hires.length})`, icon: Clock },
    { id: "history", label: "History", icon: History },
  ]

  return (
    <div className="p-6 space-y-6">
      {/* Header & Tabs */}
      <div className="stagger-item space-y-4" style={{animationDelay: "0s"}}>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{t("hiring.title")}</h1>
          <Badge variant="outline" className="gap-1">
            <Users className="size-3" /> LeaderAgent Recruitment
          </Badge>
        </div>

        <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab: Post Plan */}
      {tab === "plan" && (
        <Card className="stagger-item" style={{animationDelay: "0.08s"}}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4" />
              Hire Plan — Let Leader Dream Up Candidates
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Describe the role you need filled. The Leader agent will analyze your requirements
              and generate candidate profiles for your approval.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-1"><Briefcase className="size-3" /> Position *</Label>
                <Input value={position} onChange={e => setPosition(e.target.value)}
                  placeholder="e.g. Senior Full-Stack Engineer" />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-1"><Users className="size-3" /> Candidates</Label>
                <Input type="number" min={1} max={10} value={count}
                  onChange={e => setCount(parseInt(e.target.value) || 3)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1"><Shield className="size-3" /> Required Skills</Label>
              <Input value={skills} onChange={e => setSkills(e.target.value)}
                placeholder="e.g. React, TypeScript, Python, AWS, System Design" />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1"><Target className="size-3" /> Responsibilities</Label>
              <Textarea value={responsibilities} onChange={e => setResponsibilities(e.target.value)}
                placeholder="Describe the role's key responsibilities and expected outcomes..." className="min-h-[80px]" />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1"><BookOpen className="size-3" /> Desired Traits</Label>
              <Input value={traits} onChange={e => setTraits(e.target.value)}
                placeholder="e.g. detail-oriented, proactive, collaborative" />
            </div>
            <Button onClick={submitPlan} disabled={!position.trim() || submitting} className="gap-2">
              <Send className="size-4" />
              {submitting ? "Submitting to Leader..." : "Let Leader Dream Up Candidates"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Tab: Pending Approval */}
      {tab === "pending" && (
        <>
          {hires.length > 0 ? (
            <div className="stagger-item" style={{animationDelay: "0.08s"}}>
              <div className="flex items-center gap-2 mb-4">
                <Clock className="size-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Pending Approval ({hires.length})
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {hires.map(hire => (
                  <Card key={hire.id} className="group hover:border-primary/30 transition-colors">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <h4 className="font-semibold truncate">{hire.name}</h4>
                          <p className="text-xs text-muted-foreground">{hire.profile?.role || "Unspecified Role"}</p>
                        </div>
                        <Badge variant="secondary" className="text-[10px] shrink-0 ml-2">{hire.id}</Badge>
                      </div>

                      {hire.scene && (
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="size-3" />
                          <span>Scene: {hire.scene}</span>
                        </div>
                      )}

                      {hire.profile?.objective && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-medium text-muted-foreground uppercase">Objective</span>
                          <p className="text-xs text-muted-foreground line-clamp-2">{hire.profile.objective}</p>
                        </div>
                      )}

                      {hire.profile?.traits && hire.profile.traits.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {hire.profile.traits.map((trait: string, i: number) => (
                            <Badge key={i} variant="outline" className="text-[10px]">{trait}</Badge>
                          ))}
                        </div>
                      )}

                      {hire.profile?.background && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-medium text-muted-foreground uppercase">Background</span>
                          <p className="text-xs text-muted-foreground line-clamp-2">{hire.profile.background}</p>
                        </div>
                      )}

                      {hire.profile?.rules && hire.profile.rules.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-medium text-muted-foreground uppercase">Rules</span>
                          <div className="flex flex-wrap gap-1">
                            {hire.profile.rules.map((rule: string, i: number) => (
                              <Badge key={i} variant="secondary" className="text-[10px]">{rule}</Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex gap-2 pt-2">
                        <Button size="sm" className="flex-1 gap-1" onClick={() => setAcceptingId(hire.id)}>
                          <Check className="size-3" /> {t("hiring.approve")}
                        </Button>
                        <Button size="sm" variant="outline" className="flex-1 gap-1" onClick={() => rejectHire(hire)}>
                          <X className="size-3" /> {t("hiring.reject")}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ) : (
            <div className="stagger-item text-center py-16 text-muted-foreground" style={{animationDelay: "0.08s"}}>
              <UserPlus className="size-12 mx-auto mb-4 opacity-30" />
              <p>{t("hiring.no_pending")}</p>
              <p className="text-sm mt-1">{t("hiring.no_pending_desc")}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => setTab("plan")}>
                <Send className="size-3 mr-1" /> Post a Hiring Plan
              </Button>
            </div>
          )}
        </>
      )}

      {/* Tab: History */}
      {tab === "history" && (
        <div className="stagger-item space-y-6" style={{animationDelay: "0.08s"}}>
          {/* Approved */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <UserCheck className="size-4 text-green-500" />
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Approved ({approvedHires.length})
              </h3>
            </div>
            {approvedHires.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {approvedHires.map(hire => (
                  <Card key={hire.id} className="border-green-500/20 bg-green-50/30 dark:bg-green-950/10">
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-semibold">{hire.name}</h4>
                          <p className="text-xs text-muted-foreground">{hire.profile?.role || "—"}</p>
                        </div>
                        <Badge className="bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20 text-[10px]">
                          Hired
                        </Badge>
                      </div>
                      {hire.scene && <p className="text-xs text-muted-foreground">Scene: {hire.scene}</p>}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No approved hires yet.</p>
            )}

            {/* Rejected */}
            <div className="flex items-center gap-2 mb-3 mt-6">
              <UserX className="size-4 text-red-500" />
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Rejected ({rejectedHires.length})
              </h3>
            </div>
            {rejectedHires.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {rejectedHires.map(hire => (
                  <Card key={hire.id} className="border-red-500/20 bg-red-50/30 dark:bg-red-950/10">
                    <CardContent className="p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-semibold">{hire.name}</h4>
                          <p className="text-xs text-muted-foreground">{hire.profile?.role || "—"}</p>
                        </div>
                        <Badge variant="outline" className="text-red-600 dark:text-red-400 border-red-500/20 text-[10px]">
                          Rejected
                        </Badge>
                      </div>
                      {hire.scene && <p className="text-xs text-muted-foreground">Scene: {hire.scene}</p>}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No rejected hires.</p>
            )}
          </div>
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
