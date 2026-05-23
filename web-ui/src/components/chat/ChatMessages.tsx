import { useRef, useEffect, useState, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Loader2, ChevronDown, Wrench, CheckCircle2, XCircle,
  Brain, MessageSquare, ArrowDown, Copy, Check, Clock,
} from "lucide-react"
import { useT } from "@/context/LanguageContext"
import { useChatOverlay } from "@/context/ChatOverlayContext"
import { TOOL_DISPLAY_NAMES } from "@/lib/tool-names"
import FileCard from "./FileCard"
import type { ToolCallRecord, Message } from "@/types/chat"

interface StreamingCtrl {
  streaming: boolean
  streamText: string
  reasoningText: string
  toolCalls: ToolCallRecord[]
  toolsCollapsed: boolean
  setToolsCollapsed: (v: boolean) => void
}

interface ChatMessagesProps {
  messages: Message[]
  ctrl: StreamingCtrl
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  if (isToday) return time
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + time
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {})
}

function CodeBlock({ children }: { children: string }) {
  const [copied, setCopied] = useState(false)
  const text = String(children).replace(/\n$/, "")

  const handleCopy = useCallback(() => {
    copyToClipboard(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <div className="relative group/code">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 opacity-0 group-hover/code:opacity-100 transition-opacity p-1 rounded bg-background/50 hover:bg-background text-muted-foreground hover:text-foreground"
      >
        {copied ? <Check className="size-3 text-green-400" /> : <Copy className="size-3" />}
      </button>
      <pre><code>{children}</code></pre>
    </div>
  )
}

/** Coco mascot — the cute CC badge used as assistant avatar */
function CocoAvatar({ isKbAdmin }: { isKbAdmin?: boolean }) {
  return (
    <div className={isKbAdmin
      ? "w-8 h-8 rounded-full bg-gradient-to-br from-amber-500 to-amber-300 p-0.5 shrink-0 shadow-md"
      : "w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-300 p-0.5 shrink-0 shadow-md"
    }>
      <div className="w-full h-full rounded-full bg-white/80 flex items-center justify-center text-[10px] font-bold text-gray-700">
        CC
      </div>
    </div>
  )
}

function InlineToolCard({ tc }: { tc: ToolCallRecord }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-background/50 border border-border/50 px-3 py-2 text-[10px] animate-scaleIn">
      <div className="mt-0.5 shrink-0">
        {tc.status === "done" && <CheckCircle2 className="size-3.5 text-emerald-500" />}
        {tc.status === "error" && <XCircle className="size-3.5 text-red-500" />}
        {tc.status === "running" && <Loader2 className="size-3.5 text-blue-500 animate-spin" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <Wrench className="size-3 text-blue-500/70" />
          <span className="font-medium text-foreground/80">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
          {tc.elapsed !== undefined && (
            <span className="text-muted-foreground/60">{tc.elapsed}s</span>
          )}
          <span className={`text-[8px] px-1.5 py-0.5 rounded-full ml-auto ${
            tc.status === "running" ? "bg-blue-500/10 text-blue-400" :
            tc.status === "done" ? "bg-emerald-500/10 text-emerald-400" :
            "bg-red-500/10 text-red-400"
          }`}>{tc.status}</span>
        </div>
        {tc.arguments && (
          <div className="text-muted-foreground/60 font-mono text-[9px] mt-1 break-all bg-muted/30 rounded px-2 py-1">
            {tc.arguments.length > 150 ? tc.arguments.slice(0, 150) + "…" : tc.arguments}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatMessages({ messages, ctrl }: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(true)
  const t = useT()
  const { openFilePreview } = useChatOverlay()

  const isNearBottom = useCallback(() => {
    const el = containerRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }, [])

  const scrollToBottom = useCallback((smooth = true) => {
    endRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto" })
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onScroll = () => setAtBottom(isNearBottom())
    el.addEventListener("scroll", onScroll, { passive: true })
    return () => el.removeEventListener("scroll", onScroll)
  }, [isNearBottom])

  useEffect(() => {
    if (atBottom || ctrl.streaming) scrollToBottom(true)
  }, [messages, ctrl.streamText, ctrl.reasoningText, atBottom, ctrl.streaming, scrollToBottom])

  const isEmpty = messages.length === 0 && !ctrl.streaming

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 relative" id="chat-msgs" ref={containerRef}>
      {isEmpty && (
        <div className="flex flex-col items-center justify-center h-full text-center stagger-1 gap-3">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-blue-300 p-1 shadow-lg">
            <div className="w-full h-full rounded-full bg-white/80 flex items-center justify-center text-xl font-bold text-blue-600">CC</div>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-foreground/80">{t("chat.empty_title")}</h2>
            <p className="text-[11px] text-muted-foreground/50 mt-0.5 max-w-[200px]">
              {t("chat.empty_desc")}
            </p>
          </div>
        </div>
      )}

      {messages.map((m) => (
        <div key={m.id} className={`flex msg-enter ${m.role === "user" ? "justify-end" : "justify-start gap-2.5"}`}>
          {/* ✦ Assistant avatar */}
          {m.role === "assistant" && <CocoAvatar />}

          <div className={`${m.role === "user" ? "max-w-[80%]" : "max-w-[85%]"} space-y-1.5`}>
            {/* Reasoning / thinking */}
            {m.role === "assistant" && m.reasoningText && (
              <div className="rounded-xl border border-accent/10 bg-accent/[0.04] px-3 py-2">
                <div className="flex items-center gap-1.5 text-[9px] text-accent/70 mb-1">
                  <Brain className="size-3" />
                  {t("chat.thinking")}
                </div>
                <div className="text-[10px] text-muted-foreground/70 whitespace-pre-wrap max-h-36 overflow-y-auto leading-relaxed">
                  {m.reasoningText}
                </div>
              </div>
            )}

            {/* Tool calls — inline rich cards */}
            {m.role === "assistant" && m.tools && m.tools.length > 0 && (
              <div className="space-y-1">
                {m.tools.map(tc => <InlineToolCard key={tc.id} tc={tc} />)}
              </div>
            )}

            {/* Message bubble */}
            <div className={
              m.role === "user"
                ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-2.5 shadow-sm shadow-primary/10"
                : "bg-bubble text-foreground/85 rounded-2xl rounded-bl-md px-4 py-2.5 border border-border/60"
            }>
              <div className="markdown-content text-[11px] leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    pre: ({ children }) => <>{children}</>,
                    code: ({ className, children, ...props }) => {
                      const match = /language-(\w+)/.exec(className || "")
                      const isInline = !match && !String(children).includes("\n")
                      if (isInline) return <code className={className} {...props}>{children}</code>
                      return <CodeBlock>{String(children)}</CodeBlock>
                    },
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              </div>
            </div>

            {/* File cards */}
            {m.role === "assistant" && m.files && m.files.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-1.5">
                {m.files.map((f, i) => (
                  <FileCard
                    key={i}
                    filename={f.name}
                    fileType={f.type}
                    onClick={() => openFilePreview({ filename: f.name, content: f.url || "", type: f.type })}
                  />
                ))}
              </div>
            )}

            {/* Timestamp */}
            <div className="flex items-center gap-1 text-[9px] text-muted-foreground/40 px-1">
              <Clock className="size-2.5" />
              {formatTime(m.timestamp)}
            </div>
          </div>
        </div>
      ))}

      {/* Streaming message */}
      {ctrl.streaming && (
        <div className="flex justify-start gap-2.5">
          <CocoAvatar />
          <div className="max-w-[85%] space-y-2 w-full">
            {/* Thinking while streaming */}
            {ctrl.reasoningText && (
              <div className="rounded-xl border border-accent/10 bg-accent/[0.04] px-3 py-2">
                <div className="flex items-center gap-1.5 text-[9px] text-accent/70 mb-1">
                  <Brain className="size-3" />
                  {t("chat.thinking")}
                  <Loader2 className="size-3 animate-spin" />
                </div>
                <div className="text-[10px] text-muted-foreground/70 whitespace-pre-wrap max-h-36 overflow-y-auto">
                  {ctrl.reasoningText}
                </div>
              </div>
            )}

            {/* Streaming tool calls */}
            {ctrl.toolCalls.length > 0 && (
              <div className="space-y-1">
                <button
                  onClick={() => ctrl.setToolsCollapsed(!ctrl.toolsCollapsed)}
                  className="flex items-center gap-1.5 text-[9px] text-muted-foreground/60 hover:text-foreground transition-colors px-1"
                >
                  <ChevronDown className={`size-3 transition-transform ${ctrl.toolsCollapsed ? "" : "rotate-180"}`} />
                  {t("chat.tool_calls")} ({ctrl.toolCalls.length})
                  {ctrl.streaming && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                </button>
                {!ctrl.toolsCollapsed && (
                  <div className="space-y-1">
                    {ctrl.toolCalls.map(tc => <InlineToolCard key={tc.id} tc={tc} />)}
                  </div>
                )}
              </div>
            )}

            {/* Streaming bubble */}
            <div className="bg-bubble text-foreground/85 rounded-2xl rounded-bl-md px-4 py-3 border border-border/60">
              {ctrl.streamText ? (
                <div className="markdown-content text-[11px]">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      pre: ({ children }) => <>{children}</>,
                      code: ({ className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || "")
                        const isInline = !match && !String(children).includes("\n")
                        if (isInline) return <code className={className} {...props}>{children}</code>
                        return <CodeBlock>{String(children)}</CodeBlock>
                      },
                    }}
                  >
                    {ctrl.streamText}
                  </ReactMarkdown>
                </div>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.15s" }} />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.3s" }} />
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Scroll to bottom button */}
      {!atBottom && !ctrl.streaming && messages.length > 0 && (
        <div className="scroll-bottom-btn">
          <button
            onClick={() => scrollToBottom(true)}
            className="bg-card border border-border rounded-full p-1.5 shadow-lg hover:bg-muted transition-colors"
          >
            <ArrowDown className="size-3.5 text-muted-foreground" />
          </button>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )
}
