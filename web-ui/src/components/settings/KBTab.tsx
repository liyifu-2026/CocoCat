import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useT } from "@/context/LanguageContext"
import type { TabData } from '@/types/settings'
export function KBTab({ data, onUpdate }: { data: TabData; onUpdate: () => void }) {
  const [uploading, setUploading] = useState(false)
  const kbs = data?.kbs || []
  const t = useT()

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append("file", file)
    const kbName = kbs[0]?.id || "default"
    await fetch(`/api/knowledge/${kbName}/upload`, { method: "POST", body: form })
    setUploading(false)
    onUpdate()
  }

  return (
    <div className="space-y-4 stagger-1">
      <div className="flex gap-2 overflow-x-auto pb-2">
        {kbs.map((kb: { id: string; purpose?: string }) => (
          <button key={kb.id} className="shrink-0 rounded-full bg-secondary/10 text-secondary px-4 py-1.5 text-sm hover:bg-secondary/20 transition-all duration-200">
            {kb.id}
          </button>
        ))}
        <button className="shrink-0 rounded-full border border-dashed border-border px-4 py-1.5 text-sm text-muted-foreground/60 hover:text-foreground hover:border-foreground/30 transition-all duration-200">
          {t("kb.new")}
        </button>
      </div>

      <div className="rounded-xl border-2 border-dashed border-border p-10 text-center hover:border-muted-foreground/30 transition-colors duration-200">
        <input type="file" id="kb-upload" className="hidden" onChange={handleUpload} disabled={uploading} />
        <label htmlFor="kb-upload" className="cursor-pointer">
          <p className="text-2xl text-muted-foreground/30 mb-2">
            {uploading ? <Loader2 className="inline size-5 animate-spin" /> : "📄"}
          </p>
          <p className="text-sm text-muted-foreground/60">
            {uploading ? t("kb.uploading") : t("kb.drop_hint")}
          </p>
        </label>
      </div>

      {kbs.map((kb: { id: string; purpose?: string }) => (
        <div key={kb.id} className="text-xs text-muted-foreground/60">
          <span className="font-medium text-foreground/80">{kb.id}</span>: {kb.purpose?.slice(0, 100)}
        </div>
      ))}
    </div>
  )
}
