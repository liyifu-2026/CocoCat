import { useTheme } from "@/context/ThemeContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Sun, Moon } from "lucide-react"

export default function Settings() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader><CardTitle>Appearance</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <span className="text-sm">Theme</span>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {theme === "light" ? <Moon className="size-4 mr-1" /> : <Sun className="size-4 mr-1" />}
              {theme === "light" ? "Dark Mode" : "Light Mode"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>API Configuration</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-2 text-muted-foreground">
          <p>LLM configuration is managed server-side through .env.</p>
          <p>The frontend communicates with the FastAPI backend at /api.</p>
        </CardContent>
      </Card>
    </div>
  )
}
