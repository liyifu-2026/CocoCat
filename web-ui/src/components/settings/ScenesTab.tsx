import type { TabData } from '@/types/settings'
export function ScenesTab({ data }: { data: TabData }) {
  const scenes = data?.scenes || []
  return (
    <div className="space-y-3 stagger-1">
      {scenes.map((s: { id: string; name?: string; kbs?: string[]; skills?: string[] }) => (
        <div key={s.id} className="rounded-xl border border-border/60 p-4 hover:shadow-sm transition-shadow duration-200">
          <h3 className="text-sm font-medium text-foreground mb-2">{s.name || s.id}</h3>
          <div className="flex gap-2 flex-wrap">
            {s.kbs?.map((kb: string) => (
              <span key={kb} className="rounded-full bg-secondary/10 text-secondary px-2.5 py-0.5 text-xs">{kb}</span>
            ))}
            {s.skills?.map((sk: string) => (
              <span key={sk} className="rounded-full bg-tertiary/10 text-tertiary-foreground px-2.5 py-0.5 text-xs">{sk}</span>
            ))}
          </div>
        </div>
      ))}
      {scenes.length === 0 && (
        <p className="text-sm text-muted-foreground/60">
          No scenes configured. Create scene.yaml files in the scenes/ directory.
        </p>
      )}
    </div>
  )
}
