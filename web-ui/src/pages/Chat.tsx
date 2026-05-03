import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { chatApi } from "@/api/chat"
import type { ChatGroup, ChatMessage, GroupMember } from "@/api/chat"
import { agentsApi } from "@/api/agents"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { MessageSquare, Plus, Send, Hash, Users, Info, X, Check, Edit3 } from "lucide-react"

export default function Chat() {
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [message, setMessage] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
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
    refetchInterval: 3000,
  })

  const groups = groupsData?.groups ?? []
  const currentGroup = groups.find(g => g.id === selectedGroup)
  const messages = messagesData?.messages ?? []
  const agents = agentsData?.agents ?? []

  async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    await chatApi.sendMessage(selectedGroup, message.trim())
    setMessage("")
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
    setCreateOpen(false)
    setNewGroupName("")
    setNewGroupAnnouncement("")
    setSelectedMembers([])
  }

  function toggleMember(id: string) {
    setSelectedMembers(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
  }

  return (
    <div className="flex h-full">
      {/* Left: Groups list */}
      <div className="w-64 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Chat</h2>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button size="icon-xs" variant="ghost"><Plus className="size-4" /></Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader><DialogTitle>New Group</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Group Name</label>
                  <Input value={newGroupName} onChange={e => setNewGroupName(e.target.value)} placeholder="Group name..." />
                </div>
                <div>
                  <label className="text-sm font-medium">Announcement (optional)</label>
                  <Input value={newGroupAnnouncement} onChange={e => setNewGroupAnnouncement(e.target.value)} placeholder="Group announcement..." />
                </div>
                <div>
                  <label className="text-sm font-medium">Members</label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {agents.map(a => (
                      <button key={a.id} onClick={() => toggleMember(a.id)}
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs border transition-colors ${
                          selectedMembers.includes(a.id)
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border hover:bg-accent"
                        }`}>
                        {a.name}
                        {selectedMembers.includes(a.id) && <X className="size-3" />}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button>
                  <Button size="sm" onClick={createGroup} disabled={!newGroupName.trim()}>Create</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        <ScrollArea className="flex-1">
          {groups.map(g => (
            <button key={g.id} onClick={() => setSelectedGroup(g.id)}
              className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-accent/50 transition-colors ${
                selectedGroup === g.id ? "bg-accent" : ""
              }`}>
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                g.is_default ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}>
                <Hash className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{g.name}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {g.members.length} members
                </div>
              </div>
            </button>
          ))}
        </ScrollArea>
      </div>

      {/* Right: Conversation */}
      <div className="flex-1 flex flex-col">
        {!selectedGroup ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <MessageSquare className="size-12 mx-auto mb-4 opacity-30" />
              <p>Select a group to start chatting</p>
            </div>
          </div>
        ) : (
          <>
            {/* Group header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
              <div>
                <h2 className="font-semibold flex items-center gap-2">
                  <Hash className="size-4 text-muted-foreground" />
                  {currentGroup?.name}
                </h2>
                {currentGroup?.announcement && (
                  <p className="text-xs text-muted-foreground mt-0.5">{currentGroup.announcement}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs gap-1">
                  <Users className="size-3" /> {currentGroup?.members.length}
                </Badge>
              </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-3">
                {messages.length === 0 && (
                  <p className="text-center text-sm text-muted-foreground py-10">
                    No messages yet. Start the conversation!
                  </p>
                )}
                {messages.map((msg, i) => {
                  const isAdmin = msg.from === "admin"
                  const member = currentGroup?.members.find(m => m.id === msg.from)
                  const showAvatar = i === 0 || messages[i - 1]?.from !== msg.from
                  return (
                    <div key={i} className={`flex gap-3 ${isAdmin ? "flex-row-reverse" : ""}`}>
                      {showAvatar && (
                        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                          isAdmin ? "bg-primary text-primary-foreground" : "bg-muted"
                        }`}>
                          {member?.name?.charAt(0) ?? msg.from.charAt(0).toUpperCase()}
                        </div>
                      )}
                      {!showAvatar && <div className="w-8 shrink-0" />}
                      <div className={`max-w-[70%] ${isAdmin ? "items-end" : ""}`}>
                        {showAvatar && (
                          <div className={`text-xs text-muted-foreground mb-1 ${isAdmin ? "text-right" : ""}`}>
                            {member?.name ?? msg.from}
                            <span className="ml-2">{msg.timestamp?.slice(11, 19)}</span>
                          </div>
                        )}
                        <div className={`rounded-lg px-3 py-2 text-sm ${
                          isAdmin ? "bg-primary text-primary-foreground" : "bg-muted"
                        }`}>
                          <span className="whitespace-pre-wrap">{msg.content}</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </ScrollArea>

            {/* Input */}
            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Textarea value={message} onChange={e => setMessage(e.target.value)}
                  placeholder="Type a message... (use @name to mention)"
                  className="min-h-[40px] max-h-[120px]"
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() }
                  }}
                />
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
