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
    <Card className="fade-in" style={{ animationDelay: `${delay}ms` }}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground/60" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tracking-tight">
          {loading ? <Skeleton className="h-8 w-16" /> : value}
        </div>
      </CardContent>
    </Card>
  )
}
