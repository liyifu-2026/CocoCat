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
      <AlertCircle className="size-10 text-destructive mb-3" />
      <p className="text-muted-foreground text-sm mb-3">{message ?? t("component.failed_load")}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3 mr-1" />
          {t("component.retry")}
        </Button>
      )}
    </div>
  )
}
