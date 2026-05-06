import { createContext, useContext, useEffect, useRef, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

interface LiveUpdatesValue {}

const LiveUpdatesContext = createContext<LiveUpdatesValue | null>(null)

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000]
const DEDUPE_WINDOW = 5000

export type StreamState = {
  task_uuid: string
  event: string
  status: string
  content?: string
  stream_event?: { event_type: string; content: string; name?: string; input?: string; status?: string; result?: string }
  updatedAt: number
}
export const streamState = new Map<string, StreamState>()
export const streamListeners = new Set<() => void>()

const toastDedupe = new Map<string, number>()

function dedupedToast(key: string, message: string) {
  const last = toastDedupe.get(key)
  if (last && Date.now() - last < DEDUPE_WINDOW) return
  toastDedupe.set(key, Date.now())
  toast.info(message)
}

export function LiveUpdatesProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectIndexRef = useRef(0)
  const reconnectTimerRef = useRef<number | undefined>(undefined)
  const mountedRef = useRef(true)

  const connect = () => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const token = localStorage.getItem("cococat_token") ?? ""
    const ws = new WebSocket(`${protocol}//${location.host}/ws?token=${encodeURIComponent(token)}`)
    wsRef.current = ws

    const qc = queryClient

    ws.onopen = () => {
      reconnectIndexRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const eventType = data.type || data.event
        switch (eventType) {
          case "agent.status":
            qc.invalidateQueries({ queryKey: ["agents"] })
            if (data.status === "error") {
              dedupedToast(`agent-${data.agent_id}`, `Agent ${data.agent_id} encountered an error`)
            }
            break
          case "message.new":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            dedupedToast("message-new", `New message from ${data.from ?? "unknown"}`)
            break
          case "dispatch.update":
            qc.invalidateQueries({ queryKey: ["dispatches"] })
            break
          case "task_completed":
          case "task_failed":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            streamState.delete(data.task_uuid)
            streamListeners.forEach(fn => fn())
            break
          case "stream_progress":
          case "stream_tool":
          case "stream_reasoning":
          case "kb.progress":
          case "kb.complete":
            streamState.set(data.task_uuid, { ...data, updatedAt: Date.now() })
            streamListeners.forEach(fn => fn())
            break
        }
      } catch (err) {
        console.warn("LiveUpdates: failed to parse message", err)
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      const delay = RECONNECT_DELAYS[Math.min(reconnectIndexRef.current, RECONNECT_DELAYS.length - 1)]
      reconnectIndexRef.current++
      reconnectTimerRef.current = window.setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
      if (reconnectTimerRef.current !== undefined) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = undefined
      }
    }
  }, [queryClient])

  return (
    <LiveUpdatesContext.Provider value={{}}>
      {children}
    </LiveUpdatesContext.Provider>
  )
}

export function useLiveUpdates() {
  const ctx = useContext(LiveUpdatesContext)
  if (!ctx) throw new Error("useLiveUpdates must be used within LiveUpdatesProvider")
  return ctx
}
