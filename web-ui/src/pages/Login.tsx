import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Loader2 } from "lucide-react"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) { navigate("/chat", { replace: true }); return }
    fetch("/api/auth/status")
      .then(r => r.json())
      .then(d => setNeedsSetup(!d.has_users))
      .catch(() => setNeedsSetup(false))
  }, [isAuthenticated, navigate])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(username.trim(), password)
      navigate("/chat", { replace: true })
    } catch {
      setError("用户名或密码错误")
    } finally {
      setLoading(false)
    }
  }

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setError("")
    setLoading(true)
    try {
      const resp = await fetch("/api/auth/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}))
        setError(d.detail || "初始化失败")
        return
      }
      const data = await resp.json()
      localStorage.setItem("cococat_token", data.access_token)
      window.location.href = "/chat"
    } catch {
      setError("网络错误")
    } finally {
      setLoading(false)
    }
  }

  if (needsSetup) {
    return (
      <div className="flex items-center justify-center h-full">
        <form onSubmit={handleSetup} className="w-full max-w-sm mx-4 space-y-4">
          <div className="text-center space-y-2">
            <h1 className="text-xl font-bold">CocoCat</h1>
            <p className="text-sm text-muted-foreground">首次使用，创建管理员账户</p>
          </div>
          <input
            type="text" value={username} autoFocus placeholder="用户名"
            onChange={e => setUsername(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            type="password" value={password} placeholder="密码（至少4位）"
            onChange={e => setPassword(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <button type="submit" disabled={loading || !username.trim() || password.length < 4}
            className="w-full rounded-lg bg-primary text-primary-foreground py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-40">
            {loading ? <Loader2 className="size-4 animate-spin mx-auto" /> : "创建管理员账户"}
          </button>
        </form>
      </div>
    )
  }

  if (needsSetup === null) return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin text-muted-foreground" /></div>

  return (
    <div className="flex items-center justify-center h-full">
      <form onSubmit={handleLogin} className="w-full max-w-sm mx-4 space-y-4">
        <div className="text-center space-y-2">
          <h1 className="text-xl font-bold">CocoCat</h1>
          <p className="text-sm text-muted-foreground">登录管理面板</p>
        </div>
        <input
          type="text" value={username} autoFocus placeholder="用户名"
          onChange={e => setUsername(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <input
          type="password" value={password} placeholder="密码"
          onChange={e => setPassword(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button type="submit" disabled={loading || !username.trim() || !password.trim()}
          className="w-full rounded-lg bg-primary text-primary-foreground py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-40">
          {loading ? <Loader2 className="size-4 animate-spin mx-auto" /> : "登录"}
        </button>
      </form>
    </div>
  )
}
