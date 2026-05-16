import { useState, useEffect } from "react"
import { Save, Folder, Pencil, X, Check, FolderOpen } from "lucide-react"

interface GeneralTabProps {
  data?: { workspace?: string }
  onUpdate?: () => void
}

export function GeneralTab({ data, onUpdate }: GeneralTabProps) {
  const [value, setValue] = useState("")
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")

  useEffect(() => {
    if (data?.workspace && !value) {
      setValue(data.workspace)
    }
  }, [data?.workspace])

  useEffect(() => {
    setMsg("")
  }, [editing])

  async function handlePickFolder() {
    try {
      const resp = await fetch("/api/settings/workspace/picker", { method: "POST" })
      const data = await resp.json()
      if (data.path) {
        setValue(data.path)
        await handleSave(data.path)
      }
    } catch {
      setMsg("选择失败")
    }
  }

  async function handleSave(picked?: string) {
    const trimmed = (picked ?? value).trim()
    if (!trimmed) {
      setMsg("路径不能为空")
      return
    }
    setSaving(true)
    setMsg("")
    try {
      const resp = await fetch("/api/settings/workspace", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: trimmed }),
      })
      if (resp.ok) {
        setMsg("saved")
        setEditing(false)
        onUpdate?.()
      } else {
        setMsg("error")
      }
    } catch {
      setMsg("error")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5 stagger-1">
      <div className="rounded-xl border border-border/60 px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Folder className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">工作区目录</h3>
        </div>
        <p className="text-xs text-muted-foreground/60 mb-3">
          Agent 的文件读写操作将被限制在此目录内。保存后立即生效。
        </p>

        {editing ? (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={value}
                onChange={e => setValue(e.target.value)}
                autoFocus
                placeholder="/home/user/my-project"
                className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm font-mono text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
              />
              <button
                onClick={() => handleSave()}
                disabled={saving}
                className="h-9 px-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium flex items-center gap-1.5 hover:bg-primary/90 disabled:opacity-50 transition-all"
              >
                <Check className="size-3.5" />
                {saving ? "..." : "保存"}
              </button>
              <button
                onClick={() => {
                  setEditing(false)
                  if (data?.workspace) setValue(data.workspace)
                }}
                className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
              >
                <X className="size-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-9 px-3 rounded-lg border border-border bg-muted/30 flex items-center">
              <span className="text-sm font-mono text-foreground/80 truncate">
                {value || <span className="text-muted-foreground/40">未设置</span>}
              </span>
            </div>
            <button
              onClick={handlePickFolder}
              className="h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-accent flex items-center gap-1.5 transition-all"
            >
              <FolderOpen className="size-3.5" />
              选择
            </button>
            <button
              onClick={() => setEditing(true)}
              className="h-9 w-9 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
            >
              <Pencil className="size-3.5" />
            </button>
          </div>
        )}

        {msg && (
          <p className={`text-xs mt-2 ${msg === "saved" ? "text-emerald-500" : "text-red-500"}`}>
            {msg === "saved" ? "保存成功" : msg === "error" ? "保存失败" : msg}
          </p>
        )}
      </div>
      <div className="rounded-xl border border-border/60 px-4 py-3">
        <h3 className="text-sm font-medium text-foreground">版本</h3>
        <p className="text-xs text-muted-foreground/60 mt-0.5">CocoCat v2.0.0</p>
      </div>
    </div>
  )
}
