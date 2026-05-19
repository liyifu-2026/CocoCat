import { useState } from "react"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

interface User {
  id: string
  display_name: string
  created_at: string
}

export function UsersTab() {
  const [users, setUsers] = useState<User[]>([])
  const [loaded, setLoaded] = useState(false)
  const [newUser, setNewUser] = useState("")
  const [newPass, setNewPass] = useState("")
  const [adding, setAdding] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  const load = () => {
    fetch("/api/users")
      .then(r => r.json())
      .then(setUsers)
      .finally(() => setLoaded(true))
  }

  if (!loaded) { load(); return <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> 加载中...</div> }

  const add = async () => {
    if (!newUser.trim() || newPass.length < 4) return
    setAdding(true)
    try {
      const resp = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: newUser.trim(), password: newPass }),
      })
      if (!resp.ok) { toast.error("创建失败"); return }
      toast.success(`用户 ${newUser.trim()} 已创建`)
      setNewUser("")
      setNewPass("")
      load()
    } finally { setAdding(false) }
  }

  const remove = async (id: string) => {
    setDeleting(id)
    try {
      await fetch(`/api/users/${encodeURIComponent(id)}`, { method: "DELETE" })
      toast.success(`用户 ${id} 已删除`)
      load()
    } catch { toast.error("删除失败") }
    finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4 py-3">
      <div className="space-y-3">
        <h3 className="text-sm font-medium">用户列表</h3>
        {users.length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无用户</p>
        ) : (
          <div className="space-y-1">
            {users.map(u => (
              <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
                <div>
                  <span className="text-sm font-medium">{u.id}</span>
                  {u.display_name && u.display_name !== u.id && (
                    <span className="text-xs text-muted-foreground ml-2">({u.display_name})</span>
                  )}
                </div>
                <button onClick={() => remove(u.id)} disabled={deleting === u.id}
                  className="text-muted-foreground hover:text-destructive transition-colors p-1">
                  {deleting === u.id ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-border/50 pt-4 space-y-3">
        <h3 className="text-sm font-medium">添加用户</h3>
        <div className="flex gap-2">
          <input type="text" value={newUser} placeholder="用户名" autoComplete="off"
            onChange={e => setNewUser(e.target.value)}
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
          <input type="password" value={newPass} placeholder="密码（≥4位）" autoComplete="new-password"
            onChange={e => setNewPass(e.target.value)}
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
          <button onClick={add} disabled={adding || !newUser.trim() || newPass.length < 4}
            className="shrink-0 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 disabled:opacity-40 flex items-center gap-1.5">
            {adding ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
            添加
          </button>
        </div>
      </div>
    </div>
  )
}
