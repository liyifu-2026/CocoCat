import { createContext, useContext, useState, useMemo, type ReactNode } from "react"

interface DialogState {
  newAgentOpen: boolean
  newSceneOpen: boolean
  importSceneOpen: boolean
  newGroupOpen: boolean
}

interface DialogActions {
  openNewAgent: () => void
  closeNewAgent: () => void
  openNewScene: () => void
  closeNewScene: () => void
  openImportScene: () => void
  closeImportScene: () => void
  openNewGroup: () => void
  closeNewGroup: () => void
}

const DialogStateContext = createContext<DialogState | null>(null)
const DialogActionsContext = createContext<DialogActions | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DialogState>({
    newAgentOpen: false,
    newSceneOpen: false,
    importSceneOpen: false,
    newGroupOpen: false,
  })

  const actions = useMemo<DialogActions>(() => ({
    openNewAgent: () => setState(s => ({ ...s, newAgentOpen: true })),
    closeNewAgent: () => setState(s => ({ ...s, newAgentOpen: false })),
    openNewScene: () => setState(s => ({ ...s, newSceneOpen: true })),
    closeNewScene: () => setState(s => ({ ...s, newSceneOpen: false })),
    openImportScene: () => setState(s => ({ ...s, importSceneOpen: true })),
    closeImportScene: () => setState(s => ({ ...s, importSceneOpen: false })),
    openNewGroup: () => setState(s => ({ ...s, newGroupOpen: true })),
    closeNewGroup: () => setState(s => ({ ...s, newGroupOpen: false })),
  }), [])

  return (
    <DialogStateContext.Provider value={state}>
      <DialogActionsContext.Provider value={actions}>
        {children}
      </DialogActionsContext.Provider>
    </DialogStateContext.Provider>
  )
}

export function useDialogState() {
  const ctx = useContext(DialogStateContext)
  if (!ctx) throw new Error("useDialogState must be used within DialogProvider")
  return ctx
}

export function useDialogActions() {
  const ctx = useContext(DialogActionsContext)
  if (!ctx) throw new Error("useDialogActions must be used within DialogProvider")
  return ctx
}

export function useDialog() {
  return { ...useDialogState(), ...useDialogActions() }
}
