import type { LucideIcon } from "lucide-react"
import { Inbox } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useT } from "@/context/LanguageContext"

interface EmptyStateProps {
  icon?: LucideIcon
  title?: string
  message?: string
  action?: string
  onAction?: () => void
}

export function EmptyState({ icon: Icon = Inbox, title, message, action, onAction }: EmptyStateProps) {
  const t = useT()
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center stagger-1">
      <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mb-4">
        <Icon className="size-6 text-muted-foreground/60" />
      </div>
      {title && <h3 className="text-sm font-medium text-foreground mb-1">{title}</h3>}
      <p className="text-sm text-muted-foreground/60 max-w-[240px]">{message ?? t("component.no_data")}</p>
      {action && onAction && (
        <Button variant="outline" size="sm" className="mt-4 rounded-xl" onClick={onAction}>
          {action}
        </Button>
      )}
    </div>
  )
}
