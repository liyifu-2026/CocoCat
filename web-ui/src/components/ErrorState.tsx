import { AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useT } from "@/context/LanguageContext"

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  const t = useT()
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-2xl bg-destructive/10 flex items-center justify-center mb-4">
        <AlertCircle className="size-6 text-destructive" />
      </div>
      <p className="text-muted-foreground/70 text-sm mb-4">{message ?? t("component.failed_load")}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="rounded-xl">
          <RefreshCw className="size-3 mr-1.5" />
          {t("component.retry")}
        </Button>
      )}
    </div>
  )
}
