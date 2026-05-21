import { useCallback, useRef, useEffect } from "react"
import { useSessionStore } from "@/hooks/useSessionStore"
import { useStreaming } from "@/hooks/useStreaming"
import { useMode } from "@/context/ModeContext"
import ChatMessages from "./ChatMessages"
import ChatInput from "./ChatInput"

export default function ChatPanel() {
  const store = useSessionStore("")
  const currentIdRef = useRef(store.currentId)
  currentIdRef.current = store.currentId
  const ctrl = useStreaming(currentIdRef)
  const { currentMode, setMode } = useMode()
  const skipClearUntilId = useRef<string | null>(null)

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
          user_id: "local",
          session_id: currentIdRef.current || undefined,
          mode: currentMode,
        }),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      const reply = data.reply || "(no response)"
      if (data.mode_switch) setMode(data.mode_switch)
      const snap = ctrl.snapshot()
      store.addAssistantMessage(reply, snap)
    } catch (e) {
      store.addAssistantMessage("Error: " + String(e))
    }
    ctrl.complete()
  }, [store, ctrl, currentMode])

  return (
    <div className="w-[380px] bg-sidebar border-l border-sidebar-border flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-sidebar-border flex items-center gap-2.5">
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
        <span className="text-xs font-semibold text-foreground">Coco</span>
        <span className="text-[9px] px-2 py-0.5 rounded-full bg-primary/12 text-primary font-medium">{currentMode}</span>
      </div>

      <ChatMessages messages={store.messages} ctrl={ctrl} />

      <ChatInput onSend={sendMessage} streaming={ctrl.streaming} />
    </div>
  )
}
