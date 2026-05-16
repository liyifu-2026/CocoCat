import { createContext, useContext, useEffect, useRef, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

type MessageHandler = (data: Record<string, unknown>) => void

interface LiveUpdatesValue {
  onMessage: (type: string, handler: MessageHandler) => () => void
}

const LiveUpdatesContext = createContext<LiveUpdatesValue | null>(null)

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000]
const DEDUPE_WINDOW = 5000

const messageListeners = new Map<string, Set<MessageHandler>>()
const toastDedupe = new Map<string, number>()

function dedupedToast(key: string, message: string) {
  const last = toastDedupe.get(key)
  if (last && Date.now() - last < DEDUPE_WINDOW) return
  toastDedupe.set(key, Date.now())
  toast.info(message)
}

function getListeners(type: string): Set<MessageHandler> {
  let set = messageListeners.get(type)
  if (!set) {
    set = new Set()
    messageListeners.set(type, set)
  }
  return set
}

export function LiveUpdatesProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectIndexRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const mountedRef = useRef(true)

  const connect = () => {
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.close()
      wsRef.current = null
    }
    if (reconnectTimerRef.current !== undefined) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = undefined
    }
    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const backendHost = import.meta.env.VITE_API_HOST || `${location.hostname}:${location.port}`
    const ws = new WebSocket(`${protocol}//${backendHost}/ws`)
    wsRef.current = ws

    const qc = queryClient

    ws.onopen = () => {
      reconnectIndexRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const eventType: string = data.type || data.event

        // Dispatch to domain listeners
        getListeners(eventType).forEach(cb => cb(data.data ?? data))

        // System-level side effects (React Query invalidation, toasts)
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
            qc.invalidateQueries({ queryKey: ["knowledge"] })
            break
          case "dag.completed":
            qc.invalidateQueries({ queryKey: ["dag"] })
            break
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      const delay = RECONNECT_DELAYS[Math.min(reconnectIndexRef.current, RECONNECT_DELAYS.length - 1)]
      reconnectIndexRef.current++
      reconnectTimerRef.current = setTimeout(connect, delay)
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
    <LiveUpdatesContext.Provider value={{
      onMessage: (type: string, handler: MessageHandler) => {
        const listeners = getListeners(type)
        listeners.add(handler)
        return () => { listeners.delete(handler) }
      },
    }}>
      {children}
    </LiveUpdatesContext.Provider>
  )
}

export function useLiveUpdates() {
  const ctx = useContext(LiveUpdatesContext)
  if (!ctx) throw new Error("useLiveUpdates must be used within LiveUpdatesProvider")
  return ctx
}
