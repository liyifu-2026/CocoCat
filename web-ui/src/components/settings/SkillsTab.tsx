import type { TabData } from '@/types/settings'
export function SkillsTab({ data }: { data: TabData }) {
  const global = data?.global || []
  return (
    <div className="space-y-3 stagger-1">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Global Skills</h3>
      {global.map((s: { name: string; description: string }) => (
        <div key={s.name} className="rounded-xl border border-border/60 px-4 py-3 hover:shadow-sm transition-shadow duration-200">
          <span className="text-sm font-medium text-foreground">{s.name}</span>
          <p className="text-xs text-muted-foreground/70 mt-0.5">{s.description}</p>
        </div>
      ))}
      {global.length === 0 && (
        <p className="text-sm text-muted-foreground/60">No skills loaded. Add .md files to skills/public/.</p>
      )}
    </div>
  )
}
