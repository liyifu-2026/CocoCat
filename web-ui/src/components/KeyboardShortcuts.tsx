import { useEffect, useState } from "react"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { useT } from "@/context/LanguageContext"

export function KeyboardShortcuts() {
  const t = useT()
  const [open, setOpen] = useState(false)

  const shortcuts = [
    { keys: ["Ctrl", "K"], label: t("component.cmd_palette") },
    { keys: ["?"], label: t("component.keyboard_shortcuts") },
    { keys: ["Esc"], label: t("component.close_cancel") },
  ]

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "?" && !e.metaKey && !e.ctrlKey) {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === "INPUT" || tag === "TEXTAREA") return
        e.preventDefault()
        setOpen(o => !o)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("component.keyboard_shortcuts")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {shortcuts.map(s => (
            <div key={s.label} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{s.label}</span>
              <div className="flex items-center gap-1">
                {s.keys.map((k, i) => (
                  <span key={i} className="inline-flex items-center justify-center min-w-[24px] h-6 rounded border bg-muted px-1.5 text-xs font-mono">
                    {k}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
