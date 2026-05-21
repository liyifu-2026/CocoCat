import Bookshelf from "./Bookshelf"

export default function KbAdminFunc() {
  return (
    <div className="flex flex-col animate-view-enter">
      <Bookshelf />

      <div className="px-4 pb-4 space-y-2.5">
        <div className="bg-card border border-accent/12 rounded-xl p-3">
          <div className="text-[10px] font-semibold text-accent mb-2">⚡ Live Operations</div>
          <div className="space-y-1">
            <OpRow icon="⏳" text="Reading backend-api.md..." color="text-foreground/80" />
            <OpRow icon="✓" text="Updated Architecture wiki" />
            <OpRow icon="✓" text="Created API Design entry" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-3">
          <div className="text-[10px] font-semibold text-muted-foreground mb-2">🔧 KB Actions</div>
          <div className="flex flex-wrap gap-1.5">
            {["上传文档", "创建 Wiki", "查重/去重", "全文检索", "导出"].map(a => (
              <span key={a} className="inline-block bg-muted/50 border border-border rounded-full px-2.5 py-1 text-[9px] text-muted-foreground cursor-pointer hover:bg-muted hover:text-foreground transition-colors">
                {a}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function OpRow({ icon, text, color = "text-muted-foreground/60" }: { icon: string; text: string; color?: string }) {
  return (
    <div className={`flex items-center gap-2 text-[9px] ${color}`}>
      <span className="text-[10px]">{icon}</span>
      <span>{text}</span>
    </div>
  )
}
