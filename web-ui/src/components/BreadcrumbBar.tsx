import { useBreadcrumbs } from "@/context/BreadcrumbContext"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

export function BreadcrumbBar() {
  const { breadcrumbs } = useBreadcrumbs()

  if (breadcrumbs.length === 0) {
    return (
      <div className="flex h-12 items-center justify-end border-b border-border px-4 shrink-0">
        <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
          ⌘K
        </button>
      </div>
    )
  }

  if (breadcrumbs.length === 1) {
    return (
      <div className="flex h-12 items-center justify-between border-b border-border px-4 shrink-0">
        <h1 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          {breadcrumbs[0]!.label}
        </h1>
        <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
          ⌘K
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-12 items-center justify-between border-b border-border px-4 shrink-0">
      <Breadcrumb>
        <BreadcrumbList>
          {breadcrumbs.map((crumb, i) => (
            <BreadcrumbItem key={i}>
              {i < breadcrumbs.length - 1 ? (
                <>
                  <BreadcrumbLink href={crumb.href}>{crumb.label}</BreadcrumbLink>
                  <BreadcrumbSeparator />
                </>
              ) : (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
        ⌘K
      </button>
    </div>
  )
}
