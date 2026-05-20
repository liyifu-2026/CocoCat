import { useState, useRef, useEffect, useCallback } from "react"
import { useLiveUpdates } from "@/context/LiveUpdatesContext"
import { uuid } from "@/lib/utils"
import type { ToolCallRecord } from "@/types/chat"

interface Snapshot {
  tools: ToolCallRecord[] | undefined
  reasoningText: string | undefined
}

function matchSession(data: Record<string, unknown> | undefined, currentId: string): boolean {
  if (!currentId) return false
  if (!data?.session_id) return false
  return data.session_id === currentId
}

export function useStreaming(currentIdRef: React.MutableRefObject<string>) {
  const { onMessage } = useLiveUpdates()
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [reasoningText, setReasoningText] = useState("")
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([])
  const [toolsCollapsed, setToolsCollapsed] = useState(false)

  const streamRef = useRef("")
  const toolCallsRef = useRef<ToolCallRecord[]>([])
  const reasoningRef = useRef("")
  const streamingTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    return () => {
      clearTimeout(streamingTimeout.current)
      setStreaming(false)
    }
  }, [])

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

  const start = useCallback(() => {
    streamRef.current = ""
    setStreamText("")
    setReasoningText("")
    setToolCalls([])
    setToolsCollapsed(false)
    setStreaming(true)
    clearTimeout(streamingTimeout.current)
    streamingTimeout.current = setTimeout(() => setStreaming(false), 60000)
  }, [])

  const snapshot = useCallback((): Snapshot => ({
    tools: toolCallsRef.current.length > 0 ? [...toolCallsRef.current] : undefined,
    reasoningText: reasoningRef.current || undefined,
  }), [])

  const complete = useCallback(() => {
    clearTimeout(streamingTimeout.current)
    setStreaming(false)
    setStreamText("")
    setReasoningText("")
    setToolsCollapsed(true)
    setToolCalls([])
    streamRef.current = ""
  }, [])

  const clear = useCallback(() => {
    setToolCalls([])
    setToolsCollapsed(false)
  }, [])

  return {
    streaming,
    streamText,
    reasoningText,
    toolCalls,
    toolsCollapsed,
    setToolsCollapsed,
    start,
    snapshot,
    complete,
    clear,
  }
}
