import { useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Command } from "cmdk"
import { Search } from "lucide-react"
import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

const NAV_ITEMS: { key: string; labelKey: string; keywords: string[] }[] = [
  { key: "chat", labelKey: "nav.chat", keywords: ["chat", "message", "conversation"] },
  { key: "scenes", labelKey: "nav.scenes", keywords: ["scene", "workflow", "automation"] },
  { key: "knowledge", labelKey: "nav.knowledge", keywords: ["kb", "knowledge", "wiki"] },
  { key: "memory", labelKey: "nav.memory", keywords: ["memory", "history", "timeline"] },
  { key: "settings", labelKey: "nav.settings", keywords: ["settings", "config", "preferences"] },
]

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { modes, setMode } = useMode()
  const t = useT()

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open, onClose])

  const runCommand = useCallback((fn: () => void) => {
    fn()
    onClose()
  }, [onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[480px] rounded-xl border border-border/50 bg-popover shadow-2xl overflow-hidden animate-scaleIn" onClick={e => e.stopPropagation()}>
        <Command label="Command Menu">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
            <Search className="size-4 text-muted-foreground shrink-0" />
            <Command.Input
              autoFocus
              placeholder={t("cmd.search_placeholder")}
              className="flex-1 bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground/50"
            />
          </div>
          <Command.List className="max-h-[280px] overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-xs text-muted-foreground">{t("cmd.no_results")}</Command.Empty>

            <Command.Group heading={t("cmd.navigation")} className="text-[9px] font-semibold text-muted-foreground px-2 py-1.5">
              {NAV_ITEMS.map(item => (
                <Command.Item
                  key={item.key}
                  value={t(item.labelKey)}
                  keywords={[t(item.labelKey), ...item.keywords]}
                  onSelect={() => runCommand(() => navigate(`/${item.key}`))}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs cursor-pointer aria-selected:bg-primary/10 aria-selected:text-primary"
                >
                  {t(item.labelKey)}
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading={t("cmd.switch_mode")} className="text-[9px] font-semibold text-muted-foreground px-2 py-1.5">
              {modes.map(m => (
                <Command.Item
                  key={m.id}
                  value={m.name}
                  keywords={[m.id, m.description]}
                  onSelect={() => runCommand(() => setMode(m.id))}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs cursor-pointer aria-selected:bg-primary/10 aria-selected:text-primary"
                >
                  {m.name}
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading={t("cmd.chat_section")} className="text-[9px] font-semibold text-muted-foreground px-2 py-1.5">
              <Command.Item
                value={t("chat.new_chat")}
                keywords={["new", "chat", "session"]}
                onSelect={() => runCommand(() => navigate("/chat"))}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs cursor-pointer aria-selected:bg-primary/10 aria-selected:text-primary"
              >
                {t("cmd.new_chat_desc")}
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
