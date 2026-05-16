import { useState, useRef, useEffect, useContext, useCallback } from "react"
import { Send, Loader2, Bot, Wrench, CheckCircle2 } from "lucide-react"
import { KbChatContext, type ChatMessage } from "@/lib/KbChatContext"

function buildWsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws"
  return `${proto}://${location.host}/ws`
}

export default function KbChatPanel({ kbName }: { kbName: string }) {
  const ctx = useContext(KbChatContext)
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const messages = ctx?.messages ?? []
  const loading = ctx?.loading ?? false

  // Auto scroll
  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [messages])

  // Connect WebSocket for live streaming
  useEffect(() => {
    if (!ctx) return
    const ws = new WebSocket(buildWsUrl())
    wsRef.current = ws

    const onMessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data)
        const payload = msg.data || msg
        if (payload.agent_id !== "kb-agent") return

        if (msg.type === "text_delta" || msg.type === "stream_delta") {
          ctx.appendToLast(payload.content || "")
        } else if (msg.type === "stream_tool" || msg.type === "tool_call") {
          ctx.addToolMessage({
            type: "tool" as const,
            id: payload.tool_call_id || Date.now().toString(),
            name: payload.name || payload.tool_name || "tool",
            status: payload.status || "running",
            arguments: payload.arguments,
            result: payload.result,
            elapsed: payload.elapsed,
          })
        }
      } catch {}
    }

    ws.onmessage = onMessage
    ws.onopen = () => console.log("[kb-chat] WS connected")
    ws.onclose = () => console.log("[kb-chat] WS disconnected")

    return () => {
      ws.onmessage = null
      ws.close()
    }
  }, [])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput("")
    ctx?.addMessage({ type: "chat", role: "user", content: text })

    try {
      ctx?.setLoading(true)
      ctx?.addMessage({ type: "chat", role: "assistant", content: "" })
      const res = await fetch("/api/kb-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, kb_name: kbName }),
      })
      const data = await res.json()
      // If streaming hasn't filled the message, use REST reply
      if (data.reply) {
        const msgs = ctx?.messages
        const last = msgs?.[msgs.length - 1]
        if (last && last.type === "chat" && last.role === "assistant" && !last.content) {
          ctx?.finalizeLast(data.reply)
        }
      }
    } catch {
      ctx?.appendToLast("\n\n[Error: failed to reach kb-agent]")
    } finally {
      ctx?.setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full border-l border-border bg-card/30">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
        <Bot className="size-4 text-primary" />
        <span className="text-xs font-medium">kb-agent</span>
        {loading && <Loader2 className="size-3 animate-spin ml-auto" />}
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center pt-8">
            我是知识库管理员，可以帮你搜索、整理、维护 KB。
          </p>
        )}
        {messages.map((m, i) => {
          if (m.type === "tool") {
            return (
              <div key={i} className="flex items-center gap-2 text-[11px] text-muted-foreground py-0.5">
                <Wrench className="size-3" />
                <span className="font-mono">{m.name}</span>
                {m.status === "running" && <Loader2 className="size-3 animate-spin text-primary" />}
                {m.status === "done" && <CheckCircle2 className="size-3 text-emerald-500" />}
                {m.elapsed && <span className="text-[10px] opacity-50">({m.elapsed}s)</span>}
              </div>
            )
          }
          return (
            <div key={i} className={m.role === "user" ? "text-right" : ""}>
              <div className={`inline-block rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap ${
                m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
              }`}>
                {m.content || (m.role === "assistant" && loading && i === messages.length - 1
                  ? <span className="inline-block animate-pulse">...</span>
                  : m.content)}
              </div>
            </div>
          )
        })}
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
