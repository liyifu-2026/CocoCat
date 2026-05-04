import { Component, ReactNode } from "react"
import { AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
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
        <div className="flex flex-col items-center justify-center p-12 text-center">
          <AlertCircle className="size-12 text-destructive mb-4" />
          <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
          <p className="text-muted-foreground text-sm mb-4 max-w-md">
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <Button variant="outline" onClick={() => this.setState({ hasError: false })}>
            Try again
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
