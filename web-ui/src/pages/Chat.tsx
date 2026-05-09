import { useState, useRef, useEffect, useCallback } from "react"
import { Send, Loader2, Clock } from "lucide-react"
import { ScheduleModal } from "@/components/ScheduleModal"

interface Message {
  role: "user" | "assistant"
  content: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamText])

  // Connect WebSocket
  useEffect(() => {
    const ws = new WebSocket(`ws://${location.host}/ws`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data)
      if (event.type === "text_delta") {
        setStreamText(prev => prev + event.data.content)
      }
    }
    return () => ws.close()
  }, [])

  const send = useCallback(async () => {
    if (!input.trim() || streaming) return
    const userMsg = input.trim()
    setInput("")
    setMessages(prev => [...prev, { role: "user", content: userMsg }])
    setStreaming(true)
    setStreamText("")

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: userMsg, user_id: "local" }),
      })
      const data = await resp.json()
      const reply = data.reply || streamText || "(no response)"
      setMessages(prev => [...prev, { role: "assistant", content: reply }])
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "Error: " + String(e) }])
    }
    setStreaming(false)
    setStreamText("")
  }, [input, streaming, streamText])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-52 border-r flex flex-col">
        <button
          onClick={() => setScheduleOpen(true)}
          className="flex items-center gap-2 px-4 py-2 border-b text-sm hover:bg-muted"
        >
          <Clock className="size-4" /> 定时任务
        </button>
        <div className="flex-1 overflow-auto p-2">
          <p className="text-xs text-muted-foreground px-2 py-1">对话历史</p>
          {messages.filter(m => m.role === "user").slice(0, 20).map((m, i) => (
            <div key={i} className="text-xs px-2 py-1 truncate hover:bg-muted rounded cursor-pointer">
              {m.content.slice(0, 40)}
            </div>
          ))}
        </div>
      </div>

      {/* Main chat */}
      <div className="flex flex-col flex-1">
        <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
              m.role === "user"
                ? "bg-blue-500 text-white"
                : "bg-muted text-foreground"
            }`}>
              <pre className="whitespace-pre-wrap font-sans text-sm">{m.content}</pre>
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 bg-muted text-foreground">
              <pre className="whitespace-pre-wrap font-sans text-sm">
                {streamText || <Loader2 className="inline size-4 animate-spin" />}
              </pre>
            </div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      <div className="border-t p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Send a message..."
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1"
            rows={2}
            disabled={streaming}
          />
          <button
            onClick={send}
            disabled={streaming || !input.trim()}
            className="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 disabled:opacity-50"
          >
            {streaming ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          </button>
        </div>
      </div>
    </div>
    <ScheduleModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
  </div>
  )
}
