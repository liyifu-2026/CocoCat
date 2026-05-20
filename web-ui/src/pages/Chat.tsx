import { useState, useRef, useEffect, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Send, Loader2, Clock, MessageSquare, Trash2, ChevronDown, ChevronRight, Wrench, CheckCircle2, XCircle, Brain } from "lucide-react"
import { ScheduleModal } from "@/components/ScheduleModal"
import { TOOL_DISPLAY_NAMES } from "@/lib/tool-names"
import { useSessionStore } from "@/hooks/useSessionStore"
import { useStreaming } from "@/hooks/useStreaming"

function formatArgs(args: string | undefined): string {
  if (!args) return ""
  try {
    const parsed = JSON.parse(args)
    return JSON.stringify(parsed, null, 0).slice(0, 200)
  } catch {
    return args.slice(0, 200)
  }
}

export default function ChatPage() {
  const store = useSessionStore("")
  const currentIdRef = useRef(store.currentId)
  currentIdRef.current = store.currentId
  const ctrl = useStreaming(currentIdRef)
  const skipClearUntilId = useRef<string | null>(null)

  const [input, setInput] = useState("")
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [mode, setMode] = useState("default")
  const messagesEnd = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!store.currentId) return
    fetch(`/api/chat/history?session_id=${store.currentId}`).then(r => r.json()).then(d => {
      if (!d.messages?.length) return
      const serverMsgs = d.messages.map((m: any) => ({
        role: m.role,
        content: m.content,
      }))
      const localCount = store.messages.length
      if (serverMsgs.length > localCount) {
        store.clearMessages()
        serverMsgs.forEach((m: any) => {
          if (m.role === "user") store.addUserMessage(m.content)
          else store.addAssistantMessage(m.content)
        })
      }
    }).catch(() => {})
  }, [store.currentId])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" })
  }, [store.messages, ctrl.streamText, ctrl.reasoningText])

  const sendMessage = useCallback(async (userMsg: string) => {
    if (ctrl.streaming) return
    const hadMessages = store.messages.length > 0

    if (!store.currentId) {
      const sid = store.createSession(userMsg.slice(0, 30))
      currentIdRef.current = sid
    }
    store.addUserMessage(userMsg)
    ctrl.start()

    try {
      const body: Record<string, string | undefined> = {
        content: userMsg,
        user_id: "local",
        session_id: currentIdRef.current || undefined,
        mode,
      }
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      const reply = data.reply || "(no response)"
      const snap = ctrl.snapshot()
      store.addAssistantMessage(reply, snap)
      if (!hadMessages) {
        store.updateTitle(userMsg.slice(0, 30))
      }
    } catch (e) {
      store.addAssistantMessage("Error: " + String(e))
    }
    ctrl.complete()
  }, [store, ctrl, mode])

  useEffect(() => {
    if (skipClearUntilId.current === store.currentId) {
      skipClearUntilId.current = null
      return
    }
    if (!ctrl.streaming) {
      ctrl.clear()
    }
  }, [store.currentId, ctrl])

  const send = useCallback(async () => {
    if (!input.trim() || ctrl.streaming) return
    const userMsg = input.trim()
    setInput("")
    sendMessage(userMsg)
  }, [input, ctrl, sendMessage])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const newSession = () => { store.newSession(); ctrl.clear() }

  const deleteSession = (id: string) => {
    store.deleteSession(id)
    fetch(`/api/chat/session/${id}`, { method: "DELETE" }).catch(() => {})
  }

  return (
    <div className="flex h-full">
      <div className="w-56 border-r border-border bg-card/40 flex-col hidden md:flex">
        <div className="flex items-center justify-between px-4 h-12 border-b border-border">
          <h2 className="text-xs font-medium text-muted-foreground tracking-wider uppercase">Sessions</h2>
          <button onClick={newSession} className="text-xs bg-accent hover:bg-accent/80 text-foreground px-3 py-1 rounded-lg font-medium transition-colors">+ 新对话</button>
        </div>
        <button onClick={() => setScheduleOpen(true)} className="flex items-center gap-2.5 px-4 py-2.5 border-b border-border text-sm text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-all duration-200 group">
          <Clock className="size-4 text-tertiary" />
          <span>定时任务</span>
        </button>
        <div className="flex-1 overflow-auto p-2.5 space-y-0.5">
          {store.sessions.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center px-2">
              <MessageSquare className="size-8 text-muted-foreground/20 mb-3" />
              <p className="text-xs text-muted-foreground/40">No sessions yet</p>
            </div>
          )}
          {[...store.sessions].sort((a, b) => b.createdAt - a.createdAt).map(s => (
            <div
              key={s.id}
              className={`group flex items-center gap-2 text-xs px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 ${s.id === store.currentId ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"}`}
              onClick={() => store.selectSession(s.id)}
            >
              <span className="truncate flex-1">{s.title || "Untitled"}</span>
              <button onClick={e => { e.stopPropagation(); deleteSession(s.id) }} className="opacity-0 group-hover:opacity-100 text-muted-foreground/50 hover:text-red-500 transition-all">
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col flex-1 relative">
        <div className="flex-1 overflow-auto px-4 md:px-8 py-6 space-y-4">
          {store.messages.length === 0 && !ctrl.streaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
                <MessageSquare className="size-8 text-primary/60" />
              </div>
              <h1 className="text-lg font-display text-foreground/80 mb-2">CocoCat</h1>
              <p className="text-sm text-muted-foreground/60 max-w-xs">开始与你的 AI 团队对话</p>
            </div>
          )}

          {store.messages.map((m) => {
            const isSystemMsg = m.role === "assistant" && m.content?.startsWith("📋")
            return (
            <div key={m.id} className={`flex ${isSystemMsg ? "justify-center" : m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] md:max-w-[65%] space-y-1.5 ${m.role === "user" ? "" : "flex flex-col"}`}>
                {!isSystemMsg && m.role === "assistant" && m.reasoningText && (
                  <details className="rounded-xl border border-border/40 bg-muted/20 overflow-hidden">
                    <summary className="flex items-center gap-2 px-4 py-2 text-[11px] font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
                      <Brain className="size-3.5 text-purple-500" />
                      思考过程
                    </summary>
                    <div className="px-4 pb-3 text-xs text-muted-foreground/80 italic whitespace-pre-wrap max-h-48 overflow-y-auto">{m.reasoningText}</div>
                  </details>
                )}
                {!isSystemMsg && m.role === "assistant" && m.tools && m.tools.length > 0 && (
                  <details className="rounded-xl border border-border/40 bg-accent/20 overflow-hidden">
                    <summary className="flex items-center gap-2 px-4 py-2 text-[11px] font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
                      <Wrench className="size-3.5 text-blue-500" />
                      工具调用 ({m.tools.length})
                    </summary>
                    <div className="px-4 pb-3 space-y-1">
                      {m.tools.map(tc => (
                        <div key={tc.id} className="flex items-start gap-2.5 rounded-lg bg-accent/20 px-3 py-1.5 text-[11px]">
                          <div className="mt-0.5 shrink-0">
                            {tc.status === "done" && <CheckCircle2 className="size-3 text-green-500" />}
                            {tc.status === "error" && <XCircle className="size-3 text-red-500" />}
                            {tc.status === "running" && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                          </div>
                          <div className="flex-1 min-w-0 space-y-0.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-foreground/80">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                              {tc.elapsed !== undefined && <span className="text-[10px] text-muted-foreground/50">{tc.elapsed}s</span>}
                            </div>
                            {tc.arguments && <div className="text-muted-foreground/60 break-all font-mono text-[10px]"><span className="text-muted-foreground/30">args: </span>{formatArgs(tc.arguments)}</div>}
                            {tc.result && <div className="text-muted-foreground/60 break-all font-mono text-[10px] line-clamp-2"><span className="text-muted-foreground/30">result: </span>{tc.result}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                <div className={`${isSystemMsg ? "bg-muted/30 text-muted-foreground/70 rounded-xl px-4 py-2 text-xs text-center" : m.role === "user" ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md shadow-sm px-4 py-3" : "bg-card text-card-foreground rounded-2xl rounded-bl-md shadow-sm border border-border/50 px-4 py-3"}`}>
                  <div className="markdown-content text-sm leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            </div>
          );
        })}

          {ctrl.streaming && (
            <div className="flex justify-start">
              <div className="w-full max-w-[75%] md:max-w-[65%] space-y-2">

                {(ctrl.streaming && ctrl.reasoningText) && (
                  <div className="rounded-2xl border border-purple-500/15 bg-card overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3">
                      <Brain className="size-4 text-purple-500" />
                      <span className="text-xs font-medium">思考过程</span>
                      <Loader2 className="size-3 text-purple-500 animate-spin" />
                    </div>
                    <div className="px-4 pb-4 text-xs text-muted-foreground/80 whitespace-pre-wrap max-h-48 overflow-y-auto">{ctrl.reasoningText}</div>
                  </div>
                )}

                {ctrl.toolCalls.length > 0 && (
                  <div className="rounded-2xl border border-border/60 bg-card overflow-hidden">
                    <button
                      onClick={() => ctrl.setToolsCollapsed(!ctrl.toolsCollapsed)}
                      className="w-full flex items-center justify-between px-5 py-3 hover:bg-accent/30 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Wrench className="size-4 text-blue-500" />
                        <span className="text-xs font-medium">工具调用记录</span>
                        <span className="text-[10px] text-muted-foreground/50">{ctrl.toolCalls.length}</span>
                        {ctrl.streaming && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                      </div>
                      {ctrl.toolsCollapsed ? <ChevronRight className="size-4 text-muted-foreground" /> : <ChevronDown className="size-4 text-muted-foreground" />}
                    </button>
                    {!ctrl.toolsCollapsed && (
                      <div className="px-4 pb-4 space-y-1.5">
                        {ctrl.toolCalls.map(tc => (
                          <div key={tc.id} className="flex items-start gap-3 rounded-lg bg-accent/30 px-3 py-2 text-xs">
                            <div className="mt-0.5 shrink-0">
                              {tc.status === "running" && <Loader2 className="size-3.5 text-blue-500 animate-spin" />}
                              {tc.status === "done" && <CheckCircle2 className="size-3.5 text-green-500" />}
                              {tc.status === "error" && <XCircle className="size-3.5 text-red-500" />}
                            </div>
                            <div className="flex-1 min-w-0 space-y-0.5">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-medium text-foreground/80">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                                {tc.elapsed !== undefined && (
                                  <span className="text-[10px] text-muted-foreground/60">{tc.elapsed}s</span>
                                )}
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${tc.status === "running" ? "bg-blue-500/10 text-blue-600" : tc.status === "done" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"}`}>
                                  {tc.status}
                                </span>
                              </div>
                              {tc.arguments && (
                                <div className="text-muted-foreground/70 break-all font-mono text-[11px]">
                                  <span className="text-muted-foreground/40">args: </span>
                                  {formatArgs(tc.arguments)}
                                </div>
                              )}
                              {tc.result && (
                                <div className="text-muted-foreground/70 break-all font-mono text-[11px] line-clamp-2">
                                  <span className="text-muted-foreground/40">result: </span>
                                  {tc.result}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {ctrl.streaming && (
                  <div className="bg-card text-card-foreground rounded-2xl rounded-bl-md shadow-sm border border-border/50 px-4 py-3">
                    {ctrl.streamText ? (
                      <div className="markdown-content text-sm leading-relaxed">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {ctrl.streamText}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <span className="inline-flex gap-1">
                        <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" />
                        <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" style={{ animationDelay: "0.15s" }} />
                        <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" style={{ animationDelay: "0.3s" }} />
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEnd} />
        </div>

        <div className="border-t border-border bg-card/30 backdrop-blur-sm px-4 md:px-8 py-4">
          <div className="max-w-4xl mx-auto flex gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息..."
                className="w-full resize-none rounded-xl border border-border bg-background/80 px-4 py-3 text-sm placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
                rows={1}
                disabled={ctrl.streaming}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = "auto"
                  el.style.height = Math.min(el.scrollHeight, 160) + "px"
                }}
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={mode}
                onChange={e => setMode(e.target.value)}
                className="shrink-0 rounded-xl border border-border bg-background/60 px-3 py-3 text-xs font-medium text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 cursor-pointer"
              >
                <option value="default">Coco</option>
                <option value="kb-admin">KB 管理</option>
              </select>
              <button
                onClick={send}
                disabled={ctrl.streaming || !input.trim()}
                className="shrink-0 rounded-xl bg-primary text-primary-foreground px-5 py-3 hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 active:scale-95"
              >
                {ctrl.streaming ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
      <ScheduleModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
    </div>
  )
}
