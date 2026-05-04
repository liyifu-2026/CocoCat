import { useTheme } from "@/context/ThemeContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Sun, Moon, Server, Activity } from "lucide-react"
import { api } from "@/api/client"
import { useQuery } from "@tanstack/react-query"

export default function Settings() {
  const { theme, toggleTheme } = useTheme()

  const { data: status, isLoading } = useQuery({
    queryKey: ["settings-status"],
    queryFn: () => api.get("/status").catch(() => null),
    retry: 1,
    staleTime: 60_000,
  })

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader><CardTitle>Appearance</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Theme</p>
              <p className="text-xs text-muted-foreground">Toggle between light and dark mode</p>
            </div>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {theme === "light" ? <Moon className="size-4 mr-1" /> : <Sun className="size-4 mr-1" />}
              {theme === "light" ? "Dark Mode" : "Light Mode"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>System Status</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-1/3" />
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Server className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">Backend:</span>
                <Badge variant="secondary">Connected</Badge>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Activity className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">Status:</span>
                <Badge variant="secondary">Operational</Badge>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>LLM Configuration</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-2 text-muted-foreground">
          <p>LLM configuration is managed server-side through .env variables.</p>
          <p>The frontend communicates with the FastAPI backend at /api.</p>
        </CardContent>
      </Card>
    </div>
  )
}
