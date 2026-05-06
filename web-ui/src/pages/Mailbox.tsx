import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Image as FileImage, Table, File, Archive, Mail, MailOpen, Download, Inbox } from "lucide-react"
import { useT } from "@/context/LanguageContext"

interface DeliveryFile {
  name: string; path: string; size: number; mime: string
}

interface Delivery {
  id: string; subject: string; from_agent: string; body: string
  files: DeliveryFile[]; status: string; created_at: string
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return <FileText className="size-4 text-red-500" />
  if (['png','jpg','jpeg','gif','svg'].includes(ext || '')) return <FileImage className="size-4 text-blue-500" />
  if (['csv','xlsx','xls'].includes(ext || '')) return <Table className="size-4 text-green-500" />
  return <File className="size-4 text-muted-foreground" />
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function Mailbox() {
  const t = useT()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data } = useQuery({ queryKey: ["deliveries"], queryFn: () => api.get("/deliveries"), refetchInterval: 10000 })
  const deliveries: Delivery[] = (data as any)?.deliveries ?? []
  const selected = deliveries.find(d => d.id === selectedId)

  return (
    <div className="flex h-full">
      {/* Left: Delivery list */}
      <div className="w-80 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border">
          <h2 className="font-semibold flex items-center gap-2">
            <Inbox className="size-4" /> Inbox
          </h2>
        </div>
        <ScrollArea className="flex-1">
          {deliveries.length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-10">No deliveries yet</div>
          )}
          {deliveries.map(d => (
            <button key={d.id} onClick={() => { setSelectedId(d.id); fetch(`/api/deliveries/${d.id}/read`, {method:'POST'}) }}
              className={`flex w-full items-start gap-3 px-4 py-3 text-left text-sm hover:bg-accent/50 transition-colors border-b border-border/50 ${
                selectedId === d.id ? "bg-accent" : d.status === "new" ? "bg-primary/5" : ""
              }`}>
              <div className="shrink-0 mt-0.5">
                {d.status === "new" ? <Mail className="size-4 text-primary" /> : <MailOpen className="size-4 text-muted-foreground" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`font-medium truncate ${d.status === "new" ? "text-foreground" : "text-muted-foreground"}`}>
                    {d.subject}
                  </span>
                  <span className="text-[10px] text-muted-foreground shrink-0">
                    {new Date(d.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground truncate mt-0.5">{d.from_agent}</p>
                {d.files.length > 0 && (
                  <p className="text-[10px] text-muted-foreground mt-0.5">{d.files.length} file(s)</p>
                )}
              </div>
            </button>
          ))}
        </ScrollArea>
      </div>

      {/* Right: Detail */}
      <div className="flex-1 flex flex-col">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Inbox className="size-12 mx-auto mb-4 opacity-30" />
              <p>Select a delivery to view</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 p-6 space-y-4 overflow-auto">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold">{selected.subject}</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  From: {selected.from_agent} &middot; {new Date(selected.created_at).toLocaleString()}
                </p>
              </div>
              <Badge variant={selected.status === "new" ? "default" : "secondary"}>
                {selected.status}
              </Badge>
            </div>

            {selected.body && (
              <Card className="p-4">
                <p className="text-sm whitespace-pre-wrap">{selected.body}</p>
              </Card>
            )}

            {selected.files.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Attachments ({selected.files.length})</h3>
                <div className="space-y-2">
                  {selected.files.map(f => (
                    <div key={f.name} className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent/30 transition-colors">
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

            <div className="flex gap-2 pt-4">
              <Button variant="outline" size="sm" onClick={async () => {
                await fetch(`/api/deliveries/${selected.id}/archive`, {method:'POST'})
                queryClient.invalidateQueries({ queryKey: ["deliveries"] })
                setSelectedId(null)
              }}>
                <Archive className="size-3 mr-1" /> Archive
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
