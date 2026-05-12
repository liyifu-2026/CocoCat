import { createContext, useContext, type ReactNode } from "react"

const translations: Record<string, string> = {
  "component.no_data": "No data",
  "component.dashboard": "Dashboard",
  "component.show_sidebar": "Show sidebar",
  "component.new_scene": "New scene",
  "component.dark_mode": "Dark mode",
  "component.light_mode": "Light mode",
  "component.failed_load": "Failed to load",
  "component.retry": "Retry",
  "component.something_wrong": "Something went wrong",
  "component.unexpected_error": "An unexpected error occurred",
  "component.try_again": "Try again",
  "import_create.title": "Import or create",
}

const LanguageContext = createContext<((key: string) => string) | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const t = (key: string) => translations[key] ?? key
  return (
    <LanguageContext.Provider value={t}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useT() {
  const t = useContext(LanguageContext)
  if (!t) throw new Error("useT must be used within LanguageProvider")
  return t
}
