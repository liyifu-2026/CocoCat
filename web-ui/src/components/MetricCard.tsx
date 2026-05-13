import type { LucideIcon } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface MetricCardProps {
  label: string
  value: number | string
  icon: LucideIcon
  loading?: boolean
  delay?: number
}

export function MetricCard({ label, value, icon: Icon, loading, delay = 0 }: MetricCardProps) {
  return (
    <Card className="stagger-1 border-border/50 hover:shadow-sm transition-all duration-200" style={{ animationDelay: `${delay}ms` }}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground/40" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-display text-foreground">
          {loading ? <Skeleton className="h-8 w-16 rounded-lg" /> : value}
        </div>
      </CardContent>
    </Card>
  )
}
