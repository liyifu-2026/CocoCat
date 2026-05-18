import { useEffect, useReducer, useCallback } from "react"
import { uuid } from "@/lib/utils"
import type { Session, Message, ToolCallRecord } from "@/types/chat"

function sessionStorageKey(ns: string) { return ns ? `cococat_sessions_${ns}` : "cococat_sessions" }
function currentSessionKey(ns: string) { return ns ? `cococat_current_${ns}` : "cococat_current_session" }

interface State {
  sessions: Session[]
  currentId: string
}

type Action =
  | { type: "SELECT_SESSION"; id: string }
  | { type: "NEW_SESSION"; id: string; title: string; createdAt: number }
  | { type: "DELETE_SESSION"; id: string }
  | { type: "ADD_USER_MESSAGE"; content: string }
  | { type: "ADD_ASSISTANT_MESSAGE"; content: string; tools?: ToolCallRecord[]; dagRunIds?: string[]; reasoningText?: string }
  | { type: "UPDATE_TITLE"; title: string }
  | { type: "CLEAR_MESSAGES" }

function loadSessions(ns: string): Session[] {
  try { return JSON.parse(localStorage.getItem(sessionStorageKey(ns)) || "[]") }
  catch { return [] }
}

function saveSessions(ns: string, sessions: Session[]) {
  localStorage.setItem(sessionStorageKey(ns), JSON.stringify(sessions))
}

function loadCurrentId(ns: string): string | null {
  return localStorage.getItem(currentSessionKey(ns))
}

function saveCurrentId(ns: string, id: string) {
  localStorage.setItem(currentSessionKey(ns), id)
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SELECT_SESSION":
      return { ...state, currentId: action.id }

    case "NEW_SESSION":
      return {
        sessions: [
          ...state.sessions,
          { id: action.id, title: action.title, messages: [], createdAt: action.createdAt },
        ],
        currentId: action.id,
      }

    case "DELETE_SESSION":
      return {
        sessions: state.sessions.filter(s => s.id !== action.id),
        currentId: state.currentId === action.id ? "" : state.currentId,
      }

    case "ADD_USER_MESSAGE": {
      const msg: Message = { id: uuid(), role: "user", content: action.content }
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === state.currentId ? { ...s, messages: [...s.messages, msg] } : s
        ),
      }
    }

    case "ADD_ASSISTANT_MESSAGE": {
      const msg: Message = {
        id: uuid(),
        role: "assistant",
        content: action.content,
        tools: action.tools,
        dagRunIds: action.dagRunIds,
        reasoningText: action.reasoningText,
      }
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === state.currentId ? { ...s, messages: [...s.messages, msg] } : s
        ),
      }
    }

    case "UPDATE_TITLE":
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === state.currentId ? { ...s, title: action.title } : s
        ),
      }

    case "CLEAR_MESSAGES":
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === state.currentId ? { ...s, messages: [] } : s
        ),
      }
  }
}

function initialState(ns: string): State {
  const sessions = loadSessions(ns)
  const currentId = loadCurrentId(ns) || ""
  return { sessions, currentId }
}

export function useSessionStore(ns: string = "") {
  const [state, dispatch] = useReducer(reducer, ns, initialState)

  useEffect(() => { saveSessions(ns, state.sessions) }, [ns, state.sessions])
  useEffect(() => { saveCurrentId(ns, state.currentId) }, [ns, state.currentId])

  const current = state.sessions.find(s => s.id === state.currentId)
  const messages = current?.messages || []

  const selectSession = useCallback((id: string) => dispatch({ type: "SELECT_SESSION", id }), [])
  const newSession = useCallback(() => dispatch({ type: "SELECT_SESSION", id: "" }), [])
  const createSession = useCallback((title: string) => {
    const id = uuid()
    dispatch({ type: "NEW_SESSION", id, title, createdAt: Date.now() })
    return id
  }, [])
  const deleteSession = useCallback((id: string) => dispatch({ type: "DELETE_SESSION", id }), [])
  const clearMessages = useCallback(() => dispatch({ type: "CLEAR_MESSAGES" }), [])
  const addUserMessage = useCallback((content: string) => dispatch({ type: "ADD_USER_MESSAGE", content }), [])
  const addAssistantMessage = useCallback(
    (content: string, extras?: { tools?: ToolCallRecord[]; dagRunIds?: string[]; reasoningText?: string }) =>
      dispatch({ type: "ADD_ASSISTANT_MESSAGE", content, ...extras }),
    [],
  )
  const updateTitle = useCallback((title: string) => dispatch({ type: "UPDATE_TITLE", title }), [])

  return {
    sessions: state.sessions,
    currentId: state.currentId,
    messages,
    clearMessages,
    selectSession,
    newSession,
    createSession,
    deleteSession,
    addUserMessage,
    addAssistantMessage,
    updateTitle,
  }
}
