import { useCallback, useRef, useEffect, useState } from "react"
import { useSessionStore } from "@/hooks/useSessionStore"
import { useStreaming } from "@/hooks/useStreaming"
import { useMode } from "@/context/ModeContext"
import { useAuth } from "@/context/AuthContext"
import { useT } from "@/context/LanguageContext"
import { Trash2, MessageSquare, Plus, ChevronDown, Bell } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScheduleModal } from "@/components/ScheduleModal"
import ChatMessages from "./ChatMessages"
import ChatInput from "./ChatInput"
import type { QuickSendFn } from "../Layout"

interface ChatPanelProps {
  registerQuickSend?: (fn: QuickSendFn) => () => void
}

export default function ChatPanel({ registerQuickSend }: ChatPanelProps) {
  const store = useSessionStore("")
  const currentIdRef = useRef(store.currentId)
  const ctrl = useStreaming(currentIdRef)
  const { currentMode, setMode } = useMode()
  const { token } = useAuth()
  const skipClearUntilId = useRef<string | null>(null)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [sessionsExpanded, setSessionsExpanded] = useState(false)
  const t = useT()

  useEffect(() => {
    currentIdRef.current = store.currentId
  }, [store.currentId])

  useEffect(() => {
    if (!store.currentId) return
    fetch(`/api/chat/history?session_id=${store.currentId}`)
      .then(r => r.json())
      .then(d => {
        if (!d.messages?.length) return
        if (d.messages.length > store.messages.length) {
          store.clearMessages()
          d.messages.forEach((m: any) => {
            if (m.role === "user") store.addUserMessage(m.content)
            else store.addAssistantMessage(m.content)
          })
        }
      })
      .catch(() => {})
  }, [store.currentId])

  useEffect(() => {
    if (skipClearUntilId.current === store.currentId) {
      skipClearUntilId.current = null
      return
    }
    if (!ctrl.streaming) ctrl.clear()
  }, [store.currentId, ctrl.streaming])

  const sendMessage = useCallback(async (userMsg: string) => {
    if (ctrl.streaming) return
    if (!store.currentId) {
      const sid = store.createSession(userMsg.slice(0, 30))
      currentIdRef.current = sid
    }
    store.addUserMessage(userMsg)
    ctrl.start()

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: userMsg,
          user_id: token ? "authenticated" : "local",
          session_id: currentIdRef.current || undefined,
          mode: currentMode,
        }),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      const reply = data.reply || t("common.no_data")
      if (data.mode_switch) setMode(data.mode_switch)
      const snap = ctrl.snapshot()
      store.addAssistantMessage(reply, snap)
    } catch (e) {
      store.addAssistantMessage(t("common.error") + ": " + String(e))
    }
    ctrl.complete()
  }, [store, ctrl, currentMode])

  // Register this panel's sendMessage so parent can trigger quick-sends
  useEffect(() => {
    if (!registerQuickSend) return
    return registerQuickSend(sendMessage)
  }, [registerQuickSend, sendMessage])

  const sortedSessions = [...store.sessions].sort((a, b) => b.createdAt - a.createdAt)

  return (
    <div className="w-[420px] bg-sidebar border-l border-sidebar-border flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-sidebar-border space-y-2">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-xs font-semibold text-foreground">Coco</span>
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-primary/12 text-primary font-medium">{currentMode}</span>
          <div className="flex-1" />
          <button
            onClick={() => setScheduleOpen(true)}
            className="w-6 h-6 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-card transition-colors"
          >
            <Bell className="size-3.5" />
          </button>
          <button
            onClick={() => {
              store.createSession(t("chat.new_chat"))
              ctrl.clear()
            }}
            className="w-6 h-6 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-card transition-colors"
          >
            <Plus className="size-3.5" />
          </button>
        </div>

        {sortedSessions.length > 0 && (
          <div>
            <button
              onClick={() => setSessionsExpanded(!sessionsExpanded)}
              className="flex items-center gap-1.5 text-[9px] text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronDown className={cn("size-3 transition-transform", sessionsExpanded && "rotate-180")} />
              {t("chat.sessions")} ({sortedSessions.length})
            </button>
            {sessionsExpanded && (
              <div className="mt-1.5 max-h-[140px] overflow-y-auto space-y-0.5">
                {sortedSessions.map(s => (
                  <div
                    key={s.id}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] cursor-pointer group transition-colors",
                      s.id === store.currentId ? "bg-primary/8 text-foreground" : "text-muted-foreground hover:bg-card/50"
                    )}
                    onClick={() => store.selectSession(s.id)}
                  >
                    <MessageSquare className="size-3 shrink-0 opacity-50" />
                    <span className="truncate flex-1">{s.title || t("session.untitled")}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); store.deleteSession(s.id) }}
                      className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-400 transition-all p-0.5"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <ChatMessages messages={store.messages} ctrl={ctrl} />

      <ChatInput onSend={sendMessage} streaming={ctrl.streaming} />

      <ScheduleModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
    </div>
  )
}
