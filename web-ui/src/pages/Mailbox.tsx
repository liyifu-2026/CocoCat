import { useState, useMemo } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { agentsApi } from "@/api/agents"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AgentAvatar } from "@/components/AgentAvatar"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { toast } from "sonner"
import {
  Package, FileText, Download, CheckCircle, RotateCcw,
  Search, Inbox, ChevronDown,
} from "lucide-react"
import { useT } from "@/context/LanguageContext"

interface DeliveryFile {
  name: string; path: string; size: number; mime: string
}

interface Delivery {
  id: string; subject: string; from_agent: string; body: string
  files: DeliveryFile[]; status: string; created_at: string
}

interface DeliveryGroup {
  subject: string; from_agent: string
  versions: Delivery[]; latest: Delivery
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase()
  if (["png","jpg","jpeg","gif","svg"].includes(ext || ""))
    return <FileText className="size-4 text-blue-500" />
  if (["pdf"].includes(ext || ""))
    return <FileText className="size-4 text-red-500" />
  if (["csv","xlsx","xls"].includes(ext || ""))
    return <FileText className="size-4 text-green-500" />
  return <FileText className="size-4 text-muted-foreground" />
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const STATUS_LABELS: Record<string, string> = {
  new: "delivery.status_new",
  approved: "delivery.status_approved",
  changes_requested: "delivery.status_changes",
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-500/10 text-blue-600",
  approved: "bg-green-500/10 text-green-600",
  changes_requested: "bg-amber-500/10 text-amber-600",
}

function groupDeliveries(deliveries: Delivery[]): DeliveryGroup[] {
  const map = new Map<string, Delivery[]>()
  for (const d of deliveries) {
    const key = `${d.from_agent}::${d.subject}`
    const list = map.get(key)
    if (list) { list.push(d) } else { map.set(key, [d]) }
  }
  const groups: DeliveryGroup[] = []
  for (const [key, versions] of map) {
    versions.sort((a, b) => a.created_at.localeCompare(b.created_at))
    const parts = key.split("::")
    groups.push({
      subject: parts[1] ?? "",
      from_agent: parts[0] ?? "",
      versions,
      latest: versions[versions.length - 1]!,
    })
  }
  groups.sort((a, b) => b.latest.created_at.localeCompare(a.latest.created_at))
  return groups
}

export default function Mailbox() {
  const t = useT()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [expandedOld, setExpandedOld] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState("")

  const { data } = useQuery({
    queryKey: ["deliveries"],
    queryFn: () => api.get<{ deliveries: Delivery[] }>("/deliveries"),
    refetchInterval: 10000,
  })
  const { data: displayData } = useQuery({
    queryKey: ["agent-displays"],
    queryFn: () => agentsApi.listDisplays(),
  })

  const allGroups = useMemo(() => groupDeliveries(data?.deliveries ?? []), [data])
  const filteredGroups = useMemo(() => {
    if (!search) return allGroups
    const q = search.toLowerCase()
    return allGroups.filter(g =>
      g.subject.toLowerCase().includes(q) || g.from_agent.toLowerCase().includes(q))
  }, [allGroups, search])

  const selected = data?.deliveries?.find(d => d.id === selectedId) ?? null
  const selectedGroup = selected
    ? allGroups.find(g => g.versions.some(v => v.id === selectedId)) ?? null
    : null

  const newCount = data?.deliveries?.filter(d => d.status === "new").length ?? 0

  async function handleApprove(id: string) {
    try { await api.post(`/deliveries/${id}/approve`, {}); queryClient.invalidateQueries({ queryKey: ["deliveries"] }); toast.success(t("delivery.toast_approved")) } catch { toast.error(t("common.error")) }
  }

  return (
    <div className="flex h-full">
      {/* Left: Package list */}
      <div className="stagger-item w-80 border-r border-border flex flex-col shrink-0" style={{animationDelay: "0s"}}>
        <div className="p-4 border-b border-border space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <Package className="size-4" /> {t("delivery.title")}
            </h2>
            {newCount > 0 && (
              <Badge variant="default" className="text-xs">{t("delivery.new_count").replace("{n}", String(newCount))}</Badge>
            )}
          </div>
          <div className="relative">
            <Search className="size-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input size={1} placeholder={t("delivery.search")}
              value={search} onChange={e => setSearch(e.target.value)}
              className="pl-7 h-8 text-xs" />
          </div>
        </div>
        <ScrollArea className="flex-1">
          {filteredGroups.length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-10">
              <Inbox className="size-10 mx-auto mb-3 opacity-30" />
              {t("delivery.no_deliveries")}
            </div>
          )}
          {filteredGroups.map(g => {
            const isSelected = selectedGroup?.subject === g.subject && selectedGroup?.from_agent === g.from_agent
            return (
              <button key={`${g.from_agent}::${g.subject}`}
                onClick={() => { setSelectedId(g.latest.id); setExpandedOld(false) }}
                className={`flex w-full items-start gap-3 px-4 py-3 text-left text-sm hover:bg-accent/50 transition-colors border-b border-border/50 ${
                  isSelected ? "bg-accent" : g.latest.status === "new" ? "bg-primary/5" : ""
                }`}>
                <AgentAvatar name={g.from_agent} size="sm" />
                <div className="flex-1 min-w-0">
                  <span className={`font-medium truncate text-xs ${g.latest.status === "new" ? "text-foreground" : "text-muted-foreground"}`}>
                    {g.subject}
                  </span>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {displayData?.[g.from_agent]?.nickname || g.from_agent}
                    {" · v"}{g.versions.length}
                    {" · "}{new Date(g.latest.created_at).toLocaleDateString()}
                  </p>
                  <div className="flex items-center gap-1 mt-1">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${STATUS_COLORS[g.latest.status] || "bg-muted"}`}>
                      {t(STATUS_LABELS[g.latest.status] || g.latest.status)}
                    </span>
                    {g.versions.length > 1 && (
                      <span className="text-[9px] text-muted-foreground">+{g.versions.length - 1}</span>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </ScrollArea>
      </div>

      {/* Right: Detail */}
      <div className="stagger-item flex-1 flex flex-col" style={{animationDelay: "0.08s"}}>
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <Inbox className="size-12 mx-auto mb-4 opacity-30" />
            <p>{t("delivery.select")}</p>
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-auto">
            {/* Header */}
            <div className="px-6 py-4 border-b border-border shrink-0">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <AgentAvatar name={selected.from_agent} size="sm" />
                  <div>
                    <h2 className="text-lg font-bold">{selected.subject}</h2>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {displayData?.[selected.from_agent]?.nickname || selected.from_agent}
                      {" · "}{new Date(selected.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <Badge className={`text-xs ${STATUS_COLORS[selected.status] || ""}`}>
                  {t(STATUS_LABELS[selected.status] || selected.status)}
                </Badge>
              </div>
            </div>

            <div className="flex-1 p-6 space-y-6 overflow-auto">
              {selected.files.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <FileText className="size-3" /> {t("delivery.files")}
                  </h3>
                  <div className="space-y-2">
                    {selected.files.map(f => (
                      <div key={f.name} className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent/30">
                        {fileIcon(f.name)}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{f.name}</p>
                          <p className="text-xs text-muted-foreground">{formatSize(f.size)}</p>
                        </div>
                        <Button variant="ghost" size="icon-xs" asChild>
                          <a href={`/api/deliveries/${selected.id}/files/${f.name}`} download={f.name}>
                            <Download className="size-4" />
                          </a>
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.body && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">{t("delivery.agent_notes")}</h3>
                  <div className="p-4 rounded-lg bg-muted/50 text-sm whitespace-pre-wrap">{selected.body}</div>
                </div>
              )}

              {selectedGroup && selectedGroup.versions.length > 1 && (
                <div>
                  <button onClick={() => setExpandedOld(!expandedOld)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                    <ChevronDown className={`size-3 transition-transform ${expandedOld ? "rotate-180" : ""}`} />
                    {t("delivery.view_older")} ({selectedGroup.versions.length - 1})
                  </button>
                  {expandedOld && (
                    <div className="mt-3 space-y-3">
                      {selectedGroup.versions.filter(v => v.id !== selected.id).reverse().map(v => (
                        <div key={v.id} className="p-3 rounded-lg border border-border/50 cursor-pointer hover:bg-accent/30"
                          onClick={() => { setSelectedId(v.id); setExpandedOld(false) }}>
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium">v{selectedGroup.versions.indexOf(v) + 1}</span>
                            <span className="text-muted-foreground">{new Date(v.created_at).toLocaleString()}</span>
                          </div>
                          <div className="flex gap-2 mt-1">{v.files.map(f => (
                            <span key={f.name} className="text-[10px] text-muted-foreground">{f.name}</span>
                          ))}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="px-6 py-4 border-t border-border flex items-center gap-2 shrink-0">
              {selected.status !== "approved" && (
                <Button size="sm" onClick={() => handleApprove(selected.id)}>
                  <CheckCircle className="size-3 mr-1" /> {t("delivery.approve")}
                </Button>
              )}
              {selected.status !== "changes_requested" && (
                <Button size="sm" variant="outline" onClick={() => { setFeedbackText(""); setFeedbackOpen(true) }}>
                  <RotateCcw className="size-3 mr-1" /> {t("delivery.request_changes")}
                </Button>
              )}
              <Button size="sm" variant="outline" asChild>
                <a href={`#`} onClick={(e) => {
                  e.preventDefault()
                  selected.files.forEach(f => {
                    const a = document.createElement("a")
                    a.href = `/api/deliveries/${selected.id}/files/${f.name}`
                    a.download = f.name
                    a.click()
                  })
                }}>
                  <Download className="size-3 mr-1" /> {t("delivery.download_all")}
                </a>
              </Button>
              <div className="flex-1" />
              <Button size="sm" variant="ghost" onClick={async () => {
                setSelectedId(null)
                try { await api.post(`/deliveries/${selected.id}/archive`, {}); toast.success(t("delivery.toast_archived")) } catch { toast.error(t("common.error")) }
                queryClient.invalidateQueries({ queryKey: ["deliveries"] })
              }}>
                <Inbox className="size-3 mr-1" /> {t("common.delete")}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Feedback dialog */}
      <Dialog open={feedbackOpen} onOpenChange={setFeedbackOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>{t("delivery.request_changes")}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <Textarea value={feedbackText} onChange={e => setFeedbackText(e.target.value)}
              placeholder={t("delivery.feedback_placeholder")} className="min-h-[120px]" />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setFeedbackOpen(false)}>{t("common.cancel")}</Button>
              <Button size="sm" onClick={async () => {
                if (!selected) return
                try {
                  await api.post(`/deliveries/${selected.id}/request-changes`, { feedback: feedbackText })
                  queryClient.invalidateQueries({ queryKey: ["deliveries"] })
                  toast.success(t("delivery.toast_changes"))
                } catch { toast.error(t("common.error")) }
                setFeedbackOpen(false)
              }} disabled={!feedbackText.trim()}>
                <RotateCcw className="size-3 mr-1" /> {t("delivery.request_changes")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
