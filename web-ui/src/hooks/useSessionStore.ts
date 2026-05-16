import { useEffect, useReducer, useCallback } from "react"
import { uuid } from "@/lib/utils"
import type { Session, Message, ToolCallRecord } from "@/types/chat"

const SESSION_STORAGE_KEY = "cococat_sessions"
const CURRENT_SESSION_KEY = "cococat_current_session"

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

function loadSessions(): Session[] {
  try { return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || "[]") }
  catch { return [] }
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
  }
}

function initialState(): State {
  const sessions = loadSessions()
  const currentId = loadCurrentId() || ""
  return { sessions, currentId }
}

export function useSessionStore() {
  const [state, dispatch] = useReducer(reducer, null, initialState)

  useEffect(() => { saveSessions(state.sessions) }, [state.sessions])
  useEffect(() => { saveCurrentId(state.currentId) }, [state.currentId])

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
    selectSession,
    newSession,
    createSession,
    deleteSession,
    addUserMessage,
    addAssistantMessage,
    updateTitle,
  }
}
