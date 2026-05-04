import { AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export default function ErrorState({ message = "Failed to load data", onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <AlertCircle className="size-10 text-destructive mb-3" />
      <p className="text-muted-foreground text-sm mb-3">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3 mr-1" />
          Retry
        </Button>
      )}
    </div>
  )
}
