import { useState, useRef, useEffect } from "react"
import { Send, Loader2, Bot } from "lucide-react"

interface Message {
  role: "user" | "assistant"
  content: string
}

export default function KbChatPanel({ kbName }: { kbName: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput("")
    setMessages(prev => [...prev, { role: "user", content: text }])
    setLoading(true)

    try {
      const res = await fetch("/api/kb-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, kb_name: kbName }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: "assistant", content: data.reply || "No response" }])
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Error: failed to reach kb-agent" }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full border-l border-border bg-card/30">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
        <Bot className="size-4 text-primary" />
        <span className="text-xs font-medium">kb-agent</span>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center pt-8">
            我是知识库管理员，可以帮你搜索、整理、维护 KB。
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div className={`inline-block rounded-lg px-3 py-2 max-w-[85%] ${
              m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            kb-agent 思考中...
          </div>
        )}
      </div>
      <div className="p-2 border-t border-border shrink-0">
        <div className="flex gap-1">
          <input
            className="flex-1 bg-background border border-border rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="问 kb-agent..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send()}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="p-1.5 rounded-md hover:bg-accent disabled:opacity-30"
          >
            <Send className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
