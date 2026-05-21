import { useRef, useEffect, useState, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Loader2, ChevronRight, ChevronDown, Wrench,
  CheckCircle2, XCircle, Brain, MessageSquare,
  ArrowDown, Copy, Check
} from "lucide-react"
import { TOOL_DISPLAY_NAMES } from "@/lib/tool-names"
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

function formatArgs(args: string | undefined): string {
  if (!args) return ""
  try {
    return JSON.stringify(JSON.parse(args), null, 0).slice(0, 200)
  } catch { return args.slice(0, 200) }
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

export default function ChatMessages({ messages, ctrl }: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(true)

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

    const onScroll = () => {
      setAtBottom(isNearBottom())
    }
    el.addEventListener("scroll", onScroll, { passive: true })
    return () => el.removeEventListener("scroll", onScroll)
  }, [isNearBottom])

  useEffect(() => {
    if (atBottom || ctrl.streaming) {
      scrollToBottom(true)
    }
  }, [messages, ctrl.streamText, ctrl.reasoningText, atBottom, ctrl.streaming, scrollToBottom])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3.5 relative" id="chat-msgs" ref={containerRef}>
      {messages.length === 0 && !ctrl.streaming && (
        <div className="flex flex-col items-center justify-center h-full text-center stagger-1">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <MessageSquare className="size-6 text-primary/60" />
          </div>
          <h2 className="text-sm font-semibold text-foreground/70 mb-1">Coco</h2>
          <p className="text-[11px] text-muted-foreground/50 max-w-[200px]">
            Your workshop operator. Type a message to begin.
          </p>
        </div>
      )}

      {messages.map((m) => (
        <div key={m.id} className={`flex msg-enter ${m.role === "user" ? "justify-end" : "justify-start"}`}>
          <div className={`max-w-[85%] space-y-1.5 ${m.role === "user" ? "" : "w-full max-w-[85%]"}`}>
            {m.role === "assistant" && m.reasoningText && (
              <details className="rounded-xl border border-accent/15 bg-accent/5 overflow-hidden">
                <summary className="flex items-center gap-2 px-4 py-2 text-[10px] font-medium text-accent cursor-pointer">
                  <Brain className="size-3" />
                  思考过程
                </summary>
                <div className="px-4 pb-3 text-[10px] text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto">{m.reasoningText}</div>
              </details>
            )}
            {m.role === "assistant" && m.tools && m.tools.length > 0 && (
              <details className="rounded-xl border border-border bg-card/50 overflow-hidden">
                <summary className="flex items-center gap-2 px-4 py-2 text-[10px] font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
                  <Wrench className="size-3 text-blue-500" />
                  工具调用 ({m.tools.length})
                </summary>
                <div className="px-4 pb-3 space-y-1">
                  {m.tools.map(tc => (
                    <div key={tc.id} className="flex items-start gap-2 rounded-lg bg-accent/10 px-3 py-1.5 text-[10px]">
                      <div className="mt-0.5 shrink-0">
                        {tc.status === "done" && <CheckCircle2 className="size-3 text-green-500" />}
                        {tc.status === "error" && <XCircle className="size-3 text-red-500" />}
                        {tc.status === "running" && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-foreground/70">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                        {tc.elapsed !== undefined && <span className="text-muted-foreground/50 ml-1">{tc.elapsed}s</span>}
                        {tc.arguments && <div className="text-muted-foreground/50 font-mono text-[9px] mt-0.5 break-all">{formatArgs(tc.arguments)}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
            <div className={`text-[11px] leading-relaxed px-4 py-2.5 ${
              m.role === "user"
                ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md"
                : "bg-bubble text-foreground/85 rounded-2xl rounded-bl-md border border-border"
            }`}>
              <div className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    pre: ({ children }) => <>{children}</>,
                    code: ({ className, children, ...props }) => {
                      const match = /language-(\w+)/.exec(className || "")
                      const isInline = !match && !String(children).includes("\n")
                      if (isInline) {
                        return <code className={className} {...props}>{children}</code>
                      }
                      return <CodeBlock>{String(children)}</CodeBlock>
                    },
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      ))}

      {ctrl.streaming && (
        <div className="flex justify-start">
          <div className="max-w-[85%] space-y-2 w-full">
            {ctrl.reasoningText && (
              <div className="rounded-xl border border-accent/20 bg-card p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="size-3.5 text-accent" />
                  <span className="text-[10px] font-medium">思考中</span>
                  <Loader2 className="size-3 text-accent animate-spin" />
                </div>
                <div className="text-[10px] text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto">{ctrl.reasoningText}</div>
              </div>
            )}

            {ctrl.toolCalls.length > 0 && (
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <button
                  onClick={() => ctrl.setToolsCollapsed(!ctrl.toolsCollapsed)}
                  className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-accent/10 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Wrench className="size-3.5 text-blue-500" />
                    <span className="text-[10px] font-medium">工具调用</span>
                    <span className="text-[9px] text-muted-foreground">{ctrl.toolCalls.length}</span>
                    {ctrl.streaming && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                  </div>
                  {ctrl.toolsCollapsed ? <ChevronRight className="size-4 text-muted-foreground" /> : <ChevronDown className="size-4 text-muted-foreground" />}
                </button>
                {!ctrl.toolsCollapsed && (
                  <div className="px-4 pb-3 space-y-1">
                    {ctrl.toolCalls.map(tc => (
                      <div key={tc.id} className="flex items-start gap-2 rounded-lg bg-accent/10 px-3 py-2 text-[10px]">
                        <div className="mt-0.5 shrink-0">
                          {tc.status === "running" && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                          {tc.status === "done" && <CheckCircle2 className="size-3 text-green-500" />}
                          {tc.status === "error" && <XCircle className="size-3 text-red-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="font-medium">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                          {tc.elapsed !== undefined && <span className="text-muted-foreground ml-1">{tc.elapsed}s</span>}
                          <span className={`text-[9px] ml-2 px-1.5 py-0.5 rounded-full ${
                            tc.status === "running" ? "bg-blue-500/10 text-blue-400" :
                            tc.status === "done" ? "bg-green-500/10 text-green-400" :
                            "bg-red-500/10 text-red-400"
                          }`}>{tc.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="bg-bubble border border-border rounded-2xl rounded-bl-md px-4 py-3">
              {ctrl.streamText ? (
                <div className="markdown-content text-[11px]">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      pre: ({ children }) => <>{children}</>,
                      code: ({ className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || "")
                        const isInline = !match && !String(children).includes("\n")
                        if (isInline) {
                          return <code className={className} {...props}>{children}</code>
                        }
                        return <CodeBlock>{String(children)}</CodeBlock>
                      },
                    }}
                  >
                    {ctrl.streamText}
                  </ReactMarkdown>
                </div>
              ) : (
                <span className="inline-flex gap-1">
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.15s" }} />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.3s" }} />
                </span>
              )}
            </div>
          </div>
        </div>
      )}

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
