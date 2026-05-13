import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react"
import en from "@/i18n/en"
import zh from "@/i18n/zh"

type Lang = "en" | "zh"

const STORAGE_KEY = "cococat-lang"

const translations: Record<Lang, Record<string, string>> = { en, zh }

const LanguageContext = createContext<{
  t: (key: string) => string
  lang: Lang
  setLang: (lang: Lang) => void
} | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    if (typeof localStorage === "undefined") return "en"
    return (localStorage.getItem(STORAGE_KEY) as Lang) || "en"
  })

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((lang: Lang) => {
    localStorage.setItem(STORAGE_KEY, lang)
    setLangState(lang)
  }, [])

  const t = useCallback(
    (key: string) => translations[lang]?.[key] ?? key,
    [lang],
  )

  return (
    <LanguageContext.Provider value={{ t, lang, setLang }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useT() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error("useT must be used within LanguageProvider")
  return ctx.t
}

export function useLang() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error("useLang must be used within LanguageProvider")
  return { lang: ctx.lang, setLang: ctx.setLang }
}
