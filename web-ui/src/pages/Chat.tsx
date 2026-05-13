import { useState, useRef, useEffect, useCallback } from "react"
import { Send, Loader2, Clock, MessageSquare, Trash2, GitBranch, ChevronDown, ChevronRight, Circle, CheckCircle2, AlertCircle } from "lucide-react"
import { ScheduleModal } from "@/components/ScheduleModal"
import { useLiveUpdates } from "@/context/LiveUpdatesContext"
import { uuid } from "@/lib/utils"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
}

interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: number
}

const SESSION_STORAGE_KEY = "cococat_sessions"
const CURRENT_SESSION_KEY = "cococat_current_session"

function loadSessions(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || "[]")
  } catch { return [] }
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessions))
}

function loadCurrentId(): string | null {
  return localStorage.getItem(CURRENT_SESSION_KEY)
}

function saveCurrentId(id: string) {
  localStorage.setItem(CURRENT_SESSION_KEY, id)
}

export default function ChatPage() {
  const { onTextDelta, onReasoning, onToolEvent } = useLiveUpdates()
  const [sessions, setSessions] = useState<Session[]>(loadSessions)
  const [currentId, setCurrentId] = useState<string>(loadCurrentId() || "")
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [reasoningText, setReasoningText] = useState("")
  const [currentTool, setCurrentTool] = useState("")
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [dagRuns, setDagRuns] = useState<any[]>([])
  const [dagExpanded, setDagExpanded] = useState<Set<string>>(new Set())
  const messagesEnd = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const streamRef = useRef("")

  const current = sessions.find(s => s.id === currentId)
  const messages = current?.messages || []

  // Persist sessions whenever they change
  useEffect(() => {
    saveSessions(sessions)
  }, [sessions])

  useEffect(() => {
    saveCurrentId(currentId)
  }, [currentId])

  // Auto-scroll
  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamText, reasoningText])

  // WS streaming listeners
  useEffect(() => {
    return onTextDelta((text) => {
      streamRef.current += text
      setStreamText(streamRef.current)
    })
  }, [onTextDelta])

  useEffect(() => {
    return onReasoning((content) => {
      setReasoningText(prev => prev + content)
    })
  }, [onReasoning])

  useEffect(() => {
    return onToolEvent((name, status) => {
      if (status === "start") {
        setCurrentTool(name)
      } else {
        setCurrentTool("")
      }
    })
  }, [onToolEvent])

  // Poll DAG status — always active to catch task progress
  useEffect(() => {
    const poll = () => {
      fetch("/api/dag").then(r => r.json()).then(d => {
        setDagRuns(d.runs || [])
      }).catch(() => {})
    }
    poll()
    const timer = setInterval(poll, 1500)
    return () => clearInterval(timer)
  }, [])

  const updateMessages = useCallback((msgs: Message[]) => {
    setSessions(prev => prev.map(s => s.id === currentId ? { ...s, messages: msgs } : s))
  }, [currentId])

  const send = useCallback(async () => {
    if (!input.trim() || streaming) return
    const userMsg = input.trim()
    setInput("")
    streamRef.current = ""
    setStreamText("")
    setReasoningText("")
    const userMessage: Message = { id: uuid(), role: "user", content: userMsg }
    const newMessages = [...messages, userMessage]

    // Auto-create session if none exists
    if (!currentId) {
      const id = uuid()
      setCurrentId(id)
      setSessions(prev => [...prev, {
        id,
        title: userMsg.slice(0, 30),
        messages: newMessages,
        createdAt: Date.now(),
      }])
    } else {
      updateMessages(newMessages)
    }

    setStreaming(true)

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: userMsg, user_id: "local" }),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      const reply = data.reply || streamRef.current || "(no response)"
      const assistantMsg: Message = { id: uuid(), role: "assistant", content: reply }
      const final = [...(current?.messages || []), userMessage, assistantMsg]
      updateMessages(final)
      // Update session title if first message
      if (!current || current.messages.length === 0) {
        setSessions(prev => prev.map(s => s.id === currentId ? { ...s, title: userMsg.slice(0, 30) } : s))
      }
    } catch (e) {
      const errMsg: Message = { id: uuid(), role: "assistant", content: "Error: " + String(e) }
      updateMessages([...messages, userMessage, errMsg])
    }
    setStreaming(false)
    setStreamText("")
    setReasoningText("")
    setCurrentTool("")
    streamRef.current = ""
  }, [input, streaming, currentId, messages, updateMessages, current])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const newSession = () => {
    setCurrentId("")
    setStreamText("")
    setReasoningText("")
  }

  const deleteSession = (id: string) => {
    setSessions(prev => prev.filter(s => s.id !== id))
    if (id === currentId) {
      setCurrentId("")
    }
  }

  const dagToggleRun = (id: string) => {
    setDagExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const dagStatusIcon = (status: string) => {
    switch (status) {
      case "done": return <CheckCircle2 className="size-3 text-green-500 shrink-0" />
      case "running": return <Loader2 className="size-3 text-blue-500 animate-spin shrink-0" />
      case "failed": return <AlertCircle className="size-3 text-red-500 shrink-0" />
      default: return <Circle className="size-3 text-muted-foreground/30 shrink-0" />
    }
  }

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      <div className="w-56 border-r border-border bg-card/40 flex-col hidden md:flex">
        <div className="flex items-center justify-between px-4 h-12 border-b border-border">
          <h2 className="text-xs font-medium text-muted-foreground tracking-wider uppercase">Sessions</h2>
          <button onClick={newSession} className="text-xs text-primary hover:text-primary/80 font-medium transition-colors">
            + New
          </button>
        </div>
        <button
          onClick={() => setScheduleOpen(true)}
          className="flex items-center gap-2.5 px-4 py-2.5 border-b border-border text-sm text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-all duration-200 group"
        >
          <Clock className="size-4 text-tertiary" />
          <span>定时任务</span>
        </button>
        <div className="flex-1 overflow-auto p-2.5 space-y-0.5">
          {sessions.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center px-2">
              <MessageSquare className="size-8 text-muted-foreground/20 mb-3" />
              <p className="text-xs text-muted-foreground/40">No sessions yet</p>
            </div>
          )}
          {[...sessions].sort((a, b) => b.createdAt - a.createdAt).map(s => (
            <div
              key={s.id}
              className={`group flex items-center gap-2 text-xs px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 ${
                s.id === currentId ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
              }`}
              onClick={() => setCurrentId(s.id)}
            >
              <span className="truncate flex-1">{s.title || "Untitled"}</span>
              <button
                onClick={e => { e.stopPropagation(); deleteSession(s.id) }}
                className="opacity-0 group-hover:opacity-100 text-muted-foreground/50 hover:text-red-500 transition-all"
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex flex-col flex-1 relative">
        <div className="flex-1 overflow-auto px-4 md:px-8 py-6 space-y-4">
          {messages.length === 0 && !streaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
                <MessageSquare className="size-8 text-primary/60" />
              </div>
              <h1 className="text-lg font-display text-foreground/80 mb-2">CocoCat</h1>
              <p className="text-sm text-muted-foreground/60 max-w-xs">开始与你的 AI 团队对话</p>
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] md:max-w-[65%] ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md shadow-sm"
                  : "bg-card text-card-foreground rounded-2xl rounded-bl-md shadow-sm border border-border/50"
              } px-4 py-3`}>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
              </div>
            </div>
          ))}

          {streaming && (
            <div className="flex justify-start flex-col gap-2">
              {reasoningText && (
                <div className="max-w-[75%] md:max-w-[65%] bg-muted/40 text-muted-foreground rounded-xl px-4 py-2.5 text-xs italic border border-border/30">
                  <div className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider mb-1">思考中</div>
                  {reasoningText}
                </div>
              )}
              {currentTool && (
                <div className="max-w-[75%] md:max-w-[65%] bg-blue-500/10 text-blue-600 rounded-xl px-4 py-2 text-xs font-medium animate-pulse">
                  🔧 调用工具: {currentTool}
                </div>
              )}
              <div className="max-w-[75%] md:max-w-[65%] bg-card text-card-foreground rounded-2xl rounded-bl-md shadow-sm border border-border/50 px-4 py-3">
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {streamText || (
                    <span className="inline-flex gap-1">
                      <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" />
                      <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" style={{ animationDelay: "0.15s" }} />
                      <span className="size-2 rounded-full bg-muted-foreground/30 animate-pulse" style={{ animationDelay: "0.3s" }} />
                    </span>
                  )}
                </p>
              </div>
            </div>
          )}

          {/* DAG card — inline in conversation */}
          {dagRuns.length > 0 && (
            <div className="flex justify-start">
              <div className="max-w-[85%] md:max-w-[75%] bg-card text-card-foreground rounded-2xl rounded-bl-md shadow-sm border border-blue-500/20 px-5 py-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitBranch className="size-4 text-blue-500" />
                    <span className="text-xs font-medium text-foreground">任务进度</span>
                    <span className="text-[10px] text-muted-foreground/50">{dagRuns.length} run(s)</span>
                  </div>
                  {dagRuns[0] && (
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${dagRuns[0].status === "running" ? "bg-blue-500/10 text-blue-600" : dagRuns[0].status === "done" ? "bg-green-500/10 text-green-600" : "bg-muted text-muted-foreground"}`}>
                      {dagRuns[0].status}
                    </span>
                  )}
                </div>
                {dagRuns.map(run => (
                  <div key={run.run_id} className="text-xs">
                    <button onClick={() => dagToggleRun(run.run_id)} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground w-full text-left transition-colors">
                      {dagExpanded.has(run.run_id) ? <ChevronDown className="size-3 shrink-0" /> : <ChevronRight className="size-3 shrink-0" />}
                      <span className="font-mono text-[11px]">{run.run_id}</span>
                      <span className="text-[10px] text-muted-foreground/50">{run.stages?.length || 0} stages</span>
                    </button>
                    {dagExpanded.has(run.run_id) && run.stages?.map((st: any) => {
                      const doneCount = st.tasks?.filter((t: any) => t.status === "done").length || 0
                      const totalCount = st.tasks?.length || 0
                      return (
                        <div key={st.id} className="ml-5 mt-1.5 space-y-1">
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground/70">
                            <span>{st.name || st.id}</span>
                            <span className="text-muted-foreground/40">{doneCount}/{totalCount}</span>
                          </div>
                          <div className="ml-3 space-y-0.5">
                            {st.tasks?.map((t: any) => (
                              <div key={t.id} className="flex items-center gap-1.5">
                                {dagStatusIcon(t.status)}
                                <span className="text-[10px] font-mono text-foreground/70">{t.id}</span>
                                <span className="text-[10px] text-muted-foreground/50">{t.status}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div ref={messagesEnd} />
        </div>

        {/* Input area */}
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
                disabled={streaming}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = "auto"
                  el.style.height = Math.min(el.scrollHeight, 160) + "px"
                }}
              />
            </div>
            <button
              onClick={send}
              disabled={streaming || !input.trim()}
              className="shrink-0 rounded-xl bg-primary text-primary-foreground px-5 py-3 hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 active:scale-95"
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
