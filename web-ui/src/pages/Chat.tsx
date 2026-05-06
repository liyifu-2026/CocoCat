import { useState, useEffect, useCallback, useRef } from "react"
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
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  MessageSquare, Plus, Send, Hash, Users, X, Copy, Undo2, MoreHorizontal,
} from "lucide-react"
import { AgentAvatar } from "@/components/AgentAvatar"
import { useT } from "@/context/LanguageContext"
import { knowledgeApi } from "@/api/knowledge"
import { streamState, streamListeners, type StreamState } from "@/context/LiveUpdatesContext"

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
  const t = useT()
  if (msg.recalled) {
    return (
      <div className="flex justify-center py-2">
        <span className="text-xs text-muted-foreground italic">{t("chat.message_recalled")}</span>
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
            <div className={`rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors [&_p]:m-0 [&_ul]:m-0 [&_ol]:m-0 [&_pre]:mt-1 [&_pre]:mb-1 [&_code]:text-xs ${
              isAdmin ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-muted hover:bg-muted/80"
            }`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent align={isAdmin ? "end" : "start"}>
            <DropdownMenuItem onClick={() => navigator.clipboard.writeText(msg.content)}>
              <Copy className="size-3 mr-2" /> {t("chat.copy")}
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem onClick={() => onRecall(msgIndex)}>
                <Undo2 className="size-3 mr-2" /> {t("chat.recall")}
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
  const [mentionQuery, setMentionQuery] = useState("")
  const [mentionStart, setMentionStart] = useState(-1)
  const [, forceRender] = useState(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const queryClient = useQueryClient()
  const t = useT()

  const { data: groupsData } = useQuery({ queryKey: ["chat-groups"], queryFn: () => chatApi.listGroups() })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })
  const { data: messagesData, refetch: refetchMessages } = useQuery({
    queryKey: ["chat-messages", selectedGroup],
    queryFn: () => chatApi.getMessages(selectedGroup!),
    enabled: !!selectedGroup,
    refetchInterval: 15000,
  })

  const groups = groupsData?.groups ?? []
  const currentGroup = groups.find(g => g.id === selectedGroup)
  const messages = messagesData?.messages ?? []
  const agents: any[] = ((agentsData as any)?.agents ?? (Array.isArray(agentsData) ? agentsData : [])) as any[]

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messagesData, selectedGroup])

  // Mark messages as read when viewing
  useEffect(() => {
    if (!selectedGroup || !messages.length) return
    const lastMsg = messages[messages.length - 1]
    if (lastMsg) chatApi.markRead(selectedGroup, lastMsg.id, "admin", 0).catch(() => {})
  }, [selectedGroup, messages])
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

  useEffect(() => {
    const handler = () => forceRender(n => n + 1)
    streamListeners.add(handler)
    return () => { streamListeners.delete(handler) }
  }, [])

  const agentNames: Record<string, string> = {}
  agents.forEach(a => { agentNames[a.id] = displayConfs[a.id]?.nickname || a.name })
  agentNames["admin"] = "Admin"

  async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    const content = message.trim()
    setMessage("")

    const prev = queryClient.getQueryData<{ messages: ChatMessage[] }>(["chat-messages", selectedGroup])
    queryClient.setQueryData(["chat-messages", selectedGroup],
      (old: { messages: ChatMessage[] } | undefined) => ({
        messages: [...(old?.messages ?? []), {
          from: "admin",
          content,
          timestamp: new Date().toISOString(),
          mentions: [],
        }],
      })
    )

    try {
      await chatApi.sendMessage(selectedGroup, content)
    } catch {
      queryClient.setQueryData(["chat-messages", selectedGroup], prev)
      return
    }
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
  }

  async function recallMessage(msgId: number) {
    if (!selectedGroup) return
    await chatApi.recallMessage(selectedGroup, msgId)
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value
    const pos = e.target.selectionStart ?? val.length
    setMessage(val)

    const before = val.slice(0, pos)
    const atIdx = before.lastIndexOf("@")
    if (atIdx >= 0 && (atIdx === 0 || before[atIdx - 1] === " " || before[atIdx - 1] === "\n")) {
      const query = before.slice(atIdx + 1).replace(/[^a-zA-Z0-9\u4e00-\u9fff_\-]/g, "")
      setMentionQuery(query)
      setMentionStart(atIdx)
    } else {
      setMentionQuery("")
      setMentionStart(-1)
    }
  }

  function selectMention(name: string) {
    if (mentionStart < 0) return
    const before = message.slice(0, mentionStart)
    const after = message.slice(mentionStart + 1 + mentionQuery.length)
    const inserted = `@${name} `
    setMessage(before + inserted + after)
    setMentionQuery("")
    setMentionStart(-1)
    textareaRef.current?.focus()
  }

  const mentionMembers = mentionQuery
    ? (currentGroup?.members ?? []).filter(m =>
        m.id !== "admin" && m.name.toLowerCase().includes(mentionQuery.toLowerCase())
      )
    : (currentGroup?.members ?? []).filter(m => m.id !== "admin")

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

  function activeStreamState(): { state: StreamState; agentName: string } | null {
    if (!currentGroup || messages.length === 0) return null
    const agentId = selectedGroup?.startsWith("dm_")
      ? selectedGroup.replace("dm_", "")
      : currentGroup.members.find(m => m.id !== "admin")?.id
    if (!agentId) return null
    for (const s of streamState.values()) {
      if (s.status === "streaming") {
        return { state: s, agentName: agentNames[agentId] ?? agentId }
      }
    }
    return null
  }

  return (
    <div className="flex h-full">
      {/* Left sidebar: conversation list */}
      <div className="stagger-item w-72 border-r border-border flex flex-col shrink-0" style={{animationDelay: "0s"}}>
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">{t("chat.title")}</h2>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild><Button size="icon-xs" variant="ghost"><Plus className="size-4" /></Button></DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader><DialogTitle>{t("chat.new_group")}</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <div><label className="text-sm font-medium">{t("chat.group_name")}</label><Input value={newGroupName} onChange={e => setNewGroupName(e.target.value)} placeholder={t("chat.group_name_placeholder")} /></div>
                <div><label className="text-sm font-medium">{t("chat.announcement")}</label><Input value={newGroupAnnouncement} onChange={e => setNewGroupAnnouncement(e.target.value)} placeholder={t("chat.announcement_placeholder")} /></div>
                <div><label className="text-sm font-medium">{t("chat.members")}</label><div className="flex flex-wrap gap-1 mt-1">{agents.map(a => (<button key={a.id} onClick={() => toggleMember(a.id)} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs border transition-colors ${selectedMembers.includes(a.id) ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"}`}>{a.name}{selectedMembers.includes(a.id) && <X className="size-3" />}</button>))}</div></div>
                <div className="flex justify-end gap-2"><Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button><Button size="sm" onClick={createGroup} disabled={!newGroupName.trim()}>{t("common.create")}</Button></div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        <ScrollArea className="flex-1">
          {/* Channels Section */}
          {channels.length > 0 && (
            <div className="px-3 pt-3 pb-1">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("chat.channels")}</p>
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
                  </div>
                  <div className="text-xs text-muted-foreground truncate mt-0.5">
                    {t("chat.members_count").replace("{count}", String(g.members.length))}
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
                  {t("chat.direct_messages")}
                </button>
                <span className="text-[10px] text-muted-foreground">{dmGroups.length}</span>
              </div>
              {dmOpen && dmGroups.map(g => {
                const agentId = g.id.replace("dm_", "")
                const agentName = displayConfs[agentId]?.nickname || g.name
                const status = agentStatus[agentId]
                return (
                  <button key={g.id} onClick={() => setSelectedGroup(g.id)}
                    className={`flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors border-l-2 ${
                      selectedGroup === g.id
                        ? "bg-accent/50 border-primary"
                        : "border-transparent hover:bg-accent/30 hover:border-muted-foreground/30"
                    }`}>
                    <AgentAvatar name={agentName} size="xs"
                      status={status === "running" ? "idle" : status === "error" || status === "busy" ? "busy" : undefined} />
                    <span className="truncate">{agentName}</span>
                  </button>
                )
              })}
            </>
          )}
        </ScrollArea>
      </div>

      {/* Right: Conversation */}
      <div className="stagger-item flex-1 flex flex-col" style={{animationDelay: "0.08s"}}>
        {!selectedGroup ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center"><MessageSquare className="size-12 mx-auto mb-4 opacity-30" /><p>{t("chat.select_chat")}</p></div>
          </div>
        ) : (
          <>
            <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
              {selectedGroup?.startsWith("dm_") ? (() => {
                const agentId = selectedGroup.replace("dm_", "")
                const agentName = agentNames[agentId] || currentGroup?.name || agentId
                const status = agentStatus[agentId]
                return (
                  <div className="flex items-center gap-3">
                    <AgentAvatar name={agentName} size="sm"
                      status={status === "running" ? "idle" : status === "error" || status === "busy" ? "busy" : undefined} />
                    <div>
                      <h2 className="font-semibold">{agentName}</h2>
                      <p className="text-xs text-muted-foreground">
                        {status === "running" ? t("chat.online") : status === "error" ? t("chat.error") : status === "busy" ? t("chat.busy") : t("chat.offline")}
                      </p>
                    </div>
                  </div>
                )
              })() : (
                <div><h2 className="font-semibold flex items-center gap-2"><Hash className="size-4 text-muted-foreground" />{currentGroup?.name}</h2>{currentGroup?.announcement && <p className="text-xs text-muted-foreground mt-0.5">{currentGroup.announcement}</p>}</div>
              )}
              <Badge variant="outline" className="text-xs gap-1"><Users className="size-3" /> {currentGroup?.members.length}</Badge>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.length === 0 && <p className="text-center text-sm text-muted-foreground py-10">{t("chat.no_messages")}</p>}
                {messages.filter(m => !m.recalled || true).map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} isAdmin={msg.from === "admin"}
                    msgIndex={msg.id} groupId={selectedGroup} agentNames={agentNames}
                    onRecall={recallMessage} />
                ))}
                {(() => {
                  const stream = activeStreamState()
                  if (!stream) return null
                  const se = stream.state.stream_event
                  let label = "Processing..."
                  if (se) {
                    if (se.event_type === "stream_progress") label = se.content
                    else if (se.event_type === "stream_tool") label = `Tool: ${se.name}`
                    else if (se.event_type === "stream_reasoning") label = "Thinking..."
                  }
                  return (
                    <div className="flex gap-2">
                      <AgentAvatar name={stream.agentName} size="sm" />
                      <div className="bg-muted rounded-lg px-3 py-2 text-sm max-w-[70%]">
                        <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                          <span className="animate-pulse">●</span>
                          <span className="truncate">{label}</span>
                        </div>
                      </div>
                    </div>
                  )
                })()}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-border relative">
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <Textarea value={message} onChange={handleInput}
                    ref={textareaRef}
                    placeholder={selectedGroup?.startsWith("dm_") ? t("chat.type_dm").replace("{name}", currentGroup?.name ?? "") : t("chat.type_message")}
                    className="min-h-[40px] max-h-[120px]"
                    onKeyDown={e => {
                      if (mentionStart >= 0 && e.key === "Enter" && mentionMembers.length > 0) {
                        e.preventDefault()
                        selectMention(mentionMembers[0]!.name)
                        return
                      }
                      if (e.key === "Escape") { setMentionQuery(""); setMentionStart(-1); return }
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() }
                    }} />
                  {mentionStart >= 0 && mentionMembers.length > 0 && (
                    <div className="absolute bottom-full left-0 mb-1 bg-popover border border-border rounded-lg shadow-lg p-1 min-w-[160px] max-h-[200px] overflow-y-auto z-50">
                      {mentionMembers.map(m => (
                        <button key={m.id} onClick={() => selectMention(m.name)}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-sm rounded-md hover:bg-accent text-left">
                          {m.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
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