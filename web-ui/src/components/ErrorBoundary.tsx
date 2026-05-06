import { Component, ReactNode } from "react"
import { AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useT } from "@/context/LanguageContext"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

function ErrorFallback({ error, onReset }: { error?: Error; onReset: () => void }) {
  const t = useT()
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <AlertCircle className="size-12 text-destructive mb-4" />
      <h2 className="text-xl font-semibold mb-2">{t("component.something_wrong")}</h2>
      <p className="text-muted-foreground text-sm mb-4 max-w-md">
        {error?.message || t("component.unexpected_error")}
      </p>
      <Button variant="outline" onClick={onReset}>
        {t("component.try_again")}
      </Button>
    </div>
  )
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <ErrorFallback error={this.state.error} onReset={() => this.setState({ hasError: false })} />
      )
    }
    return this.props.children
  }
}
