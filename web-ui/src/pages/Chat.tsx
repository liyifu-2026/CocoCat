import { useState, useEffect, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { chatApi } from "@/api/chat"
import type { ChatGroup, ChatMessage, ReadByEntry } from "@/api/chat"
import { agentsApi } from "@/api/agents"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  MessageSquare, Plus, Send, Hash, Users, X, Copy, Undo2, MoreHorizontal,
} from "lucide-react"
import { AgentAvatar } from "@/components/AgentAvatar"

function formatTime(ts: string) {
  const d = new Date(ts)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function MessageBubble({ msg, isAdmin, msgIndex, groupId, agentNames, onRecall }: {
  msg: ChatMessage; isAdmin: boolean; msgIndex: number; groupId: string
  agentNames: Record<string, string>; onRecall: (idx: number) => void
}) {
  if (msg.recalled) {
    return (
      <div className="flex justify-center py-2">
        <span className="text-xs text-muted-foreground italic">A message was recalled</span>
      </div>
    )
  }

  const readBy = (msg.read_by ?? []).sort((a, b) => a.read_at.localeCompare(b.read_at))

  return (
    <div className={`flex gap-2 ${isAdmin ? "flex-row-reverse" : ""}`}>
      <AgentAvatar name={agentNames[msg.from] ?? msg.from} size="sm" />
      <div className={`max-w-[70%] ${isAdmin ? "items-end" : ""}`}>
        <div className={`text-xs text-muted-foreground mb-0.5 ${isAdmin ? "text-right" : ""}`}>
          {agentNames[msg.from] ?? msg.from}
          <span className="ml-2">{formatTime(msg.timestamp)}</span>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <div className={`rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
              isAdmin ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-muted hover:bg-muted/80"
            }`}>
              {msg.content}
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent align={isAdmin ? "end" : "start"}>
            <DropdownMenuItem onClick={() => navigator.clipboard.writeText(msg.content)}>
              <Copy className="size-3 mr-2" /> Copy
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem onClick={() => onRecall(msgIndex)}>
                <Undo2 className="size-3 mr-2" /> Recall
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Read receipts */}
        {readBy.length > 0 && (
          <div className={`flex gap-0.5 mt-1 ${isAdmin ? "justify-end" : ""}`}>
            {readBy.map(r => (
              <AgentAvatar key={r.agent_id}
                name={agentNames[r.agent_id] ?? r.agent_id}
                size="xs" />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [message, setMessage] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [dmOpen, setDmOpen] = useState(true)
  const [newGroupName, setNewGroupName] = useState("")
  const [newGroupAnnouncement, setNewGroupAnnouncement] = useState("")
  const [selectedMembers, setSelectedMembers] = useState<string[]>([])
  const queryClient = useQueryClient()

  const { data: groupsData } = useQuery({ queryKey: ["chat-groups"], queryFn: () => chatApi.listGroups() })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const { data: messagesData, refetch: refetchMessages } = useQuery({
    queryKey: ["chat-messages", selectedGroup],
    queryFn: () => chatApi.getMessages(selectedGroup!),
    enabled: !!selectedGroup,
    refetchInterval: 5000,
  })

  const groups = groupsData?.groups ?? []
  const currentGroup = groups.find(g => g.id === selectedGroup)
  const messages = messagesData?.messages ?? []
  const agents: any[] = ((agentsData as any)?.agents ?? (Array.isArray(agentsData) ? agentsData : [])) as any[]
  const channels = groups.filter(g => !g.id.startsWith("dm_"))
  const dmGroups = groups.filter(g => g.id.startsWith("dm_"))
  const agentStatus: Record<string, string> = {}
  ;(Array.isArray(agents) ? agents : []).forEach((a: any) => { agentStatus[a.id] = a.status })
  const [displayConfs, setDisplayConfs] = useState<Record<string, {nickname?: string}>>({})
  useEffect(() => {
    if (!agents.length) return
    agents.forEach(async (a: any) => {
      try {
        const r = await agentsApi.display(a.id)
        if (r?.nickname) setDisplayConfs(p => ({ ...p, [a.id]: { nickname: r.nickname } }))
      } catch {}
    })
  }, [agents])
  const agentNames: Record<string, string> = {}
  agents.forEach(a => { agentNames[a.id] = displayConfs[a.id]?.nickname || a.name })
  agentNames["admin"] = "Admin"

  async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    await chatApi.sendMessage(selectedGroup, message.trim())
    setMessage("")
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
  }

  async function recallMessage(msgIndex: number) {
    if (!selectedGroup) return
    await chatApi.recallMessage(selectedGroup, msgIndex)
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
  }

  async function createGroup() {
    if (!newGroupName.trim()) return
    const members = selectedMembers.map(id => {
      const a = agents.find(x => x.id === id)
      return { id, name: a?.name ?? id, role: "member" as const }
    })
    await chatApi.createGroup(newGroupName.trim(), members, newGroupAnnouncement)
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
    setCreateOpen(false); setNewGroupName(""); setNewGroupAnnouncement(""); setSelectedMembers([])
  }

  function toggleMember(id: string) {
    setSelectedMembers(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])
  }

  return (
    <div className="flex h-full">
      {/* Left sidebar: conversation list */}
      <div className="w-72 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Chat</h2>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild><Button size="icon-xs" variant="ghost"><Plus className="size-4" /></Button></DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader><DialogTitle>New Group</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <div><label className="text-sm font-medium">Group Name</label><Input value={newGroupName} onChange={e => setNewGroupName(e.target.value)} placeholder="Group name..." /></div>
                <div><label className="text-sm font-medium">Announcement</label><Input value={newGroupAnnouncement} onChange={e => setNewGroupAnnouncement(e.target.value)} placeholder="Group announcement..." /></div>
                <div><label className="text-sm font-medium">Members</label><div className="flex flex-wrap gap-1 mt-1">{agents.map(a => (<button key={a.id} onClick={() => toggleMember(a.id)} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs border transition-colors ${selectedMembers.includes(a.id) ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"}`}>{a.name}{selectedMembers.includes(a.id) && <X className="size-3" />}</button>))}</div></div>
                <div className="flex justify-end gap-2"><Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button><Button size="sm" onClick={createGroup} disabled={!newGroupName.trim()}>Create</Button></div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        <ScrollArea className="flex-1">
          {/* Channels Section */}
          {channels.length > 0 && (
            <div className="px-3 pt-3 pb-1">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Channels</p>
            </div>
          )}
          {channels.map(g => (
            <button key={g.id} onClick={() => setSelectedGroup(g.id)}
              className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-accent/50 transition-colors ${selectedGroup === g.id ? "bg-accent" : ""}`}>
              <div className="relative shrink-0">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${g.is_default ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                  <Hash className="size-5" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-medium truncate">{g.name}</span>
                  {messagesData?.messages?.slice(-1)[0] && (
                    <span className="text-xs text-muted-foreground shrink-0 ml-2">{formatTime(messagesData!.messages.slice(-1)[0]!.timestamp)}</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate mt-0.5">
                  {(() => {
                    const last = messagesData?.messages?.slice(-1)[0]
                    return last ? (last.recalled ? "[recalled]" : last.content) : `${g.members.length} members`
                  })()}
                </div>
              </div>
            </button>
          ))}

          {/* DM Section - collapsible */}
          {dmGroups.length > 0 && (
            <>
              <div className="px-3 pt-4 pb-1 flex items-center justify-between">
                <button onClick={() => setDmOpen(o => !o)} className="flex items-center gap-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors">
                  <span className={`transition-transform duration-150 ${dmOpen ? "rotate-90" : ""}`}>▶</span>
                  Direct Messages
                </button>
                <span className="text-[10px] text-muted-foreground">{dmGroups.length}</span>
              </div>
              {dmOpen && dmGroups.map(g => {
                const agentId = g.id.replace("dm_", "")
                const agentName = displayConfs[agentId]?.nickname || g.name
                const status = agentStatus[agentId]
                return (
                  <button key={g.id} onClick={() => setSelectedGroup(g.id)}
                    className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors border-l-2 ${
                      selectedGroup === g.id
                        ? "bg-accent/50 border-primary"
                        : "border-transparent hover:bg-accent/30 hover:border-muted-foreground/30"
                    }`}>
                    <span className={`shrink-0 w-2 h-2 rounded-full ${
                      status === "running" ? "bg-green-500" : status === "error" || status === "busy" ? "bg-red-500" : "bg-muted-foreground/30"
                    }`} />
                    <span className="truncate">{agentName}</span>
                  </button>
                )
              })}
            </>
          )}
        </ScrollArea>
      </div>

      {/* Right: Conversation */}
      <div className="flex-1 flex flex-col">
        {!selectedGroup ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center"><MessageSquare className="size-12 mx-auto mb-4 opacity-30" /><p>Select a group to start chatting</p></div>
          </div>
        ) : (
          <>
            <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
              {selectedGroup?.startsWith("dm_") ? (
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${
                    agentStatus[selectedGroup.replace("dm_", "")] === "running" ? "bg-green-500"
                    : agentStatus[selectedGroup.replace("dm_", "")] === "error" || agentStatus[selectedGroup.replace("dm_", "")] === "busy" ? "bg-red-500"
                    : "bg-muted-foreground/30"
                  }`} />
                  <h2 className="font-semibold">{currentGroup?.name}</h2>
                  <span className="text-xs text-muted-foreground">· DM</span>
                </div>
              ) : (
                <div><h2 className="font-semibold flex items-center gap-2"><Hash className="size-4 text-muted-foreground" />{currentGroup?.name}</h2>{currentGroup?.announcement && <p className="text-xs text-muted-foreground mt-0.5">{currentGroup.announcement}</p>}</div>
              )}
              <Badge variant="outline" className="text-xs gap-1"><Users className="size-3" /> {currentGroup?.members.length}</Badge>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.length === 0 && <p className="text-center text-sm text-muted-foreground py-10">No messages yet</p>}
                {messages.filter(m => !m.recalled || true).map((msg, i) => (
                  <MessageBubble key={i} msg={msg} isAdmin={msg.from === "admin"}
                    msgIndex={i} groupId={selectedGroup} agentNames={agentNames}
                    onRecall={recallMessage} />
                ))}
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Textarea value={message} onChange={e => setMessage(e.target.value)}
                  placeholder={selectedGroup?.startsWith("dm_") ? `Message ${currentGroup?.name}...` : "Type a message... (use @name to mention)"}
                  className="min-h-[40px] max-h-[120px]"
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() } }} />
                <Button onClick={sendMessage} disabled={!message.trim()} className="shrink-0 self-end">
                  <Send className="size-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}