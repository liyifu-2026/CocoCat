import { useState, useRef, useEffect, useCallback } from "react"
import { useLiveUpdates } from "@/context/LiveUpdatesContext"
import { uuid } from "@/lib/utils"
import type { ToolCallRecord } from "@/types/chat"

interface Snapshot {
  tools: ToolCallRecord[] | undefined
  dagRunIds: string[] | undefined
  reasoningText: string | undefined
}

function matchSession(data: Record<string, unknown> | undefined, currentId: string): boolean {
  if (!currentId) return false
  if (!data?.session_id) return true // no session_id in payload → accept
  return data.session_id === currentId
}

export function useStreaming(currentIdRef: React.MutableRefObject<string>) {
  const { onMessage } = useLiveUpdates()
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [reasoningText, setReasoningText] = useState("")
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([])
  const [dagRuns, setDagRuns] = useState<any[]>([])
  const [turnDagRuns, setTurnDagRuns] = useState<any[]>([])
  const [turnDagExpanded, setTurnDagExpanded] = useState(false)
  const [toolsCollapsed, setToolsCollapsed] = useState(false)
  const [allDagRuns, setAllDagRuns] = useState<any[]>([])

  const streamRef = useRef("")
  const toolCallsRef = useRef<ToolCallRecord[]>([])
  const reasoningRef = useRef("")
  const turnDagRunsRef = useRef<any[]>([])
  const preStreamRunIds = useRef<Set<string>>(new Set())

  // WS streaming listeners — wired once, stable callbacks, session-filtered
  useEffect(() => {
    return onMessage("text_delta", (data) => {
      if (!matchSession(data, currentIdRef.current)) return
      const text = (data?.content as string) ?? ""
      streamRef.current += text
      setStreamText(streamRef.current)
    })
  }, [onMessage])

  useEffect(() => {
    return onMessage("stream_reasoning", (data) => {
      if (!matchSession(data, currentIdRef.current)) return
      const content = (data?.content as string) ?? ""
      setReasoningText(prev => {
        const next = prev + content
        reasoningRef.current = next
        return next
      })
    })
  }, [onMessage])

  useEffect(() => {
    return onMessage("stream_tool", (data) => {
      if (!matchSession(data, currentIdRef.current)) return
      const name = (data?.name as string) ?? ""
      const status = (data?.status as string) ?? ""
      const callId = data?.tool_call_id as string | undefined
      setToolCalls(prev => {
        let next: ToolCallRecord[]
        if (status === "start") {
          next = [...prev, {
            id: uuid(),
            name,
            status: "running",
            toolCallId: callId,
            arguments: data?.arguments as string | undefined,
          }]
        } else {
          next = prev.map(tc =>
            (callId ? tc.toolCallId === callId : tc.name === name && tc.status === "running")
              ? {
                  ...tc,
                  status: status === "done" ? "done" : "error",
                  result: data?.result as string | undefined,
                  elapsed: data?.elapsed as number | undefined,
                }
              : tc
          )
        }
        toolCallsRef.current = next
        return next
      })
    })
  }, [onMessage])

  // Poll DAG — session-filtered (1.5s)
  useEffect(() => {
    const poll = () => {
      const sid = currentIdRef.current
      const params = sid ? `?session_id=${sid}` : ""
      fetch(`/api/dag${params}`).then(r => r.json()).then(d => {
        setDagRuns(d.runs || [])
      }).catch(() => {})
    }
    poll()
    const timer = setInterval(poll, 1500)
    return () => clearInterval(timer)
  }, [currentIdRef])

  // Poll DAG — global (3s)
  useEffect(() => {
    const poll = () => {
      fetch("/api/dag").then(r => r.json()).then(d => {
        setAllDagRuns(d.runs || [])
      }).catch(() => {})
    }
    poll()
    const timer = setInterval(poll, 3000)
    return () => clearInterval(timer)
  }, [])

  // Feed new DAG runs into current turn during streaming
  useEffect(() => {
    if (!streaming) return
    const newRuns = dagRuns.filter(run => !preStreamRunIds.current.has(run.run_id))
    setTurnDagRuns(newRuns)
    turnDagRunsRef.current = newRuns
    if (newRuns.length > 0) setTurnDagExpanded(true)
  }, [dagRuns, streaming])

  const start = useCallback((existingDagRuns: any[]) => {
    streamRef.current = ""
    setStreamText("")
    setReasoningText("")
    setToolCalls([])
    setToolsCollapsed(false)
    setTurnDagRuns([])
    preStreamRunIds.current = new Set(existingDagRuns.map((r: any) => r.run_id))
    setStreaming(true)
  }, [])

  const snapshot = useCallback((): Snapshot => ({
    tools: toolCallsRef.current.length > 0 ? [...toolCallsRef.current] : undefined,
    dagRunIds: turnDagRunsRef.current.length > 0
      ? turnDagRunsRef.current.map((r: any) => r.run_id)
      : undefined,
    reasoningText: reasoningRef.current || undefined,
  }), [])

  const complete = useCallback(() => {
    setStreaming(false)
    setStreamText("")
    setReasoningText("")
    setToolsCollapsed(true)
    setTurnDagExpanded(false)
    setToolCalls([])
    setTurnDagRuns([])
    streamRef.current = ""
  }, [])

  const clear = useCallback(() => {
    setToolCalls([])
    setTurnDagRuns([])
    setTurnDagExpanded(false)
    setToolsCollapsed(false)
  }, [])

  const dismissCompleted = useCallback(() => {
    setAllDagRuns(prev => prev.filter((r: any) => r.status === "running"))
  }, [])

  const jumpToDagSession = useCallback((sessionId: string | undefined) => {
    if (!sessionId) return
    const runs = allDagRuns.filter((r: any) => r.session_id === sessionId)
    setTurnDagRuns(runs)
    setTurnDagExpanded(true)
  }, [allDagRuns])

  return {
    streaming,
    streamText,
    reasoningText,
    toolCalls,
    dagRuns,
    turnDagRuns,
    turnDagExpanded,
    setTurnDagExpanded,
    toolsCollapsed,
    setToolsCollapsed,
    allDagRuns,
    start,
    snapshot,
    complete,
    clear,
    dismissCompleted,
    jumpToDagSession,
  }
}
