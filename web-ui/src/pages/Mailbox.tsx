import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { mailboxApi } from "@/api/mailbox"
import { agentsApi } from "@/api/agents"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Mail, MailOpen } from "lucide-react"

export default function Mailbox() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [message, setMessage] = useState("")
  const queryClient = useQueryClient()

  const { data: mailboxData } = useQuery({ queryKey: ["mailbox"], queryFn: () => mailboxApi.list() })
  const { data: messagesData, refetch: refetchMessages } = useQuery({
    queryKey: ["mailbox", selectedId],
    queryFn: () => mailboxApi.getMessages(selectedId!),
    enabled: !!selectedId,
  })
  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() })

  const mailboxes = mailboxData?.mailboxes ?? []
  const selectedMailbox = mailboxes.find(m => m.agent_id === selectedId)
  const messages = messagesData?.messages ?? []

  async function selectAgent(agentId: string) {
    setSelectedId(agentId)
    setMessage("")
    // Mark as read when selected
    await mailboxApi.markRead(agentId)
    queryClient.invalidateQueries({ queryKey: ["mailbox"] })
    refetchMessages()
  }

  async function sendMessage() {
    if (!selectedId || !message.trim()) return
    await mailboxApi.send(selectedId, message.trim())
    setMessage("")
    queryClient.invalidateQueries({ queryKey: ["mailbox", selectedId] })
    queryClient.invalidateQueries({ queryKey: ["mailbox"] })
  }

  return (
    <div className="flex h-full">
      {/* Left: Agent list */}
      <div className="w-64 border-r border-border flex flex-col shrink-0">
        <div className="p-4 border-b border-border">
          <h2 className="font-semibold">Mailboxes</h2>
        </div>
        <ScrollArea className="flex-1">
          {mailboxes.map(mb => (
            <button
              key={mb.agent_id}
              onClick={() => selectAgent(mb.agent_id)}
              className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-accent/50 transition-colors ${
                selectedId === mb.agent_id ? "bg-accent" : ""
              }`}
            >
              <div className="relative shrink-0">
                {mb.unread > 0 ? (
                  <Mail className="size-4 text-primary" />
                ) : (
                  <MailOpen className="size-4 text-muted-foreground" />
                )}
                {mb.unread > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground px-1">
                    {mb.unread > 99 ? "99+" : mb.unread}
                  </span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{mb.name}</div>
                {mb.latest && (
                  <div className="text-xs text-muted-foreground truncate mt-0.5">
                    [{mb.latest.from}] {mb.latest.content}
                  </div>
                )}
              </div>
            </button>
          ))}
        </ScrollArea>
      </div>

      {/* Right: Conversation */}
      <div className="flex-1 flex flex-col">
        {!selectedId ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Select an agent to view their mailbox
          </div>
        ) : (
          <>
            <div className="p-4 border-b border-border">
              <h2 className="font-semibold">{selectedMailbox?.name ?? selectedId}</h2>
              <p className="text-xs text-muted-foreground">ID: {selectedId}</p>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-3">
                {messages.length === 0 && (
                  <p className="text-center text-sm text-muted-foreground py-10">No messages yet</p>
                )}
                {messages.slice().reverse().map((msg, i) => (
                  <div key={i} className={`flex ${msg.from === "admin" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] rounded-lg px-4 py-2 text-sm ${
                      msg.from === "admin"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}>
                      <div className="text-xs opacity-70 mb-1">
                        {msg.from === "admin" ? "You" : msg.from}
                        <span className="ml-2">{msg.timestamp?.slice(11, 19)}</span>
                      </div>
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Textarea
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  placeholder="Type a message..."
                  className="min-h-[40px] max-h-[120px]"
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      sendMessage()
                    }
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
