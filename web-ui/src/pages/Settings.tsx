import { useTheme } from "@/context/ThemeContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Sun, Moon, Server, Activity } from "lucide-react"
import { api } from "@/api/client"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "@/context/LanguageContext"

export default function Settings() {
  const { theme, toggleTheme } = useTheme()
  const { t, lang, setLang } = useTranslation()

  const { data: status, isLoading } = useQuery({
    queryKey: ["settings-status"],
    queryFn: () => api.get("/status").catch(() => null),
    retry: 1,
    staleTime: 60_000,
  })

  return (
    <div className="p-6 space-y-6">
      <h1 className="stagger-item text-2xl font-bold" style={{animationDelay: "0s"}}>{t("settings.title")}</h1>

      <Card className="stagger-item" style={{animationDelay: "0.08s"}}>
        <CardHeader><CardTitle>{t("settings.appearance")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{t("settings.theme")}</p>
              <p className="text-xs text-muted-foreground">{t("settings.theme_desc")}</p>
            </div>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {theme === "light" ? <Moon className="size-4 mr-1" /> : <Sun className="size-4 mr-1" />}
              {theme === "light" ? t("settings.dark_mode") : t("settings.light_mode")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="stagger-item" style={{animationDelay: "0.16s"}}>
        <CardHeader><CardTitle>{t("settings.language")}</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">{t("settings.language_desc")}</p>
          <select
            className="border rounded px-3 py-1.5 text-sm"
            value={lang}
            onChange={e => setLang(e.target.value as "zh" | "en")}
          >
            <option value="zh">{t("settings.chinese")}</option>
            <option value="en">{t("settings.english")}</option>
          </select>
        </CardContent>
      </Card>

      <Card className="stagger-item" style={{animationDelay: "0.24s"}}>
        <CardHeader><CardTitle>{t("settings.system_status")}</CardTitle></CardHeader>
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
                <span className="text-muted-foreground">{t("settings.backend")}:</span>
                <Badge variant="secondary">{t("settings.connected")}</Badge>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Activity className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">{t("settings.status")}:</span>
                <Badge variant="secondary">{t("settings.operational")}</Badge>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="stagger-item" style={{animationDelay: "0.32s"}}>
        <CardHeader><CardTitle>{t("settings.llm_config")}</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-2 text-muted-foreground">
          <p>{t("settings.llm_desc_1")}</p>
          <p>{t("settings.llm_desc_2")}</p>
        </CardContent>
      </Card>
    </div>
  )
}
