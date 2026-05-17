import { useState, useEffect, useRef } from "react"
import { X, Circle, Eye, EyeOff, Loader2, QrCode } from "lucide-react"
import type { ChannelTypeInfo, MainChannelInfo, ChannelConfigField } from "@/types/settings"
import { CHANNEL_ICONS } from "@/lib/channel-icons"

interface ChannelDrawerProps {
  open: boolean
  onClose: () => void
  typeInfo: ChannelTypeInfo
  mainInfo?: MainChannelInfo
  onSave: (channelType: string, config: Record<string, string>) => Promise<void>
  onConnect: (channelType: string) => Promise<void>
  onDisconnect: (channelType: string) => Promise<void>
}

interface QrState {
  qrcode_url: string
  qrcode_id: string
  status: string
}

const CAP_LABELS: Record<string, string> = {
  text: "文字", image: "图片", voice: "语音", file: "文件", video: "视频",
  card: "卡片", sticker: "表情", link: "链接", post: "富文本", event: "事件", location: "位置",
}

const QR_STATUS_LABELS: Record<string, string> = {
  waiting: "等待扫码",
  scanned: "已扫码, 确认中...",
  confirmed: "登录成功",
  expired: "二维码已过期",
  timeout: "二维码已超时",
}

function FieldInput({ field, value, onChange }: {
  field: ChannelConfigField
  value: string
  onChange: (v: string) => void
}) {
  const [show, setShow] = useState(false)
  const isPw = field.type === "password" && !show

  return (
    <div className="mb-3">
      <label className="block text-[11px] font-medium text-foreground mb-1.5">
        {field.label} {field.required && <span className="text-red-500">*</span>}
      </label>
      <div className="flex gap-1.5">
        <input
          type={isPw ? "password" : "text"}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/30"
        />
        {field.type === "password" && (
          <button onClick={() => setShow(!show)} className="shrink-0 rounded-lg border border-border bg-background px-2.5 text-xs hover:bg-accent transition-colors">
            {show ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </button>
        )}
      </div>
    </div>
  )
}

export function ChannelDrawer({ open, onClose, typeInfo, mainInfo, onSave, onConnect, onDisconnect }: ChannelDrawerProps) {
  const IconComp = CHANNEL_ICONS[typeInfo.channel_type]
  const status = mainInfo?.status ?? "unconfigured"

  const initialConfig: Record<string, string> = {}
  for (const f of typeInfo.config_fields) {
    initialConfig[f.key] = ""
  }
  const [config, setConfig] = useState<Record<string, string>>(initialConfig)
  const [saving, setSaving] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState("")

  // QR polling state
  const [qrState, setQrState] = useState<QrState | null>(null)
  const [qrPolling, setQrPolling] = useState(false)
  const qrTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Cleanup QR polling on unmount or close
  useEffect(() => {
    return () => {
      if (qrTimerRef.current) clearInterval(qrTimerRef.current)
    }
  }, [])

  const stopQrPolling = () => {
    if (qrTimerRef.current) {
      clearInterval(qrTimerRef.current)
      qrTimerRef.current = null
    }
    setQrPolling(false)
  }

  const startQrPolling = () => {
    stopQrPolling()
    setQrPolling(true)
    const poll = async () => {
      try {
        const resp = await fetch(`/api/channels/qr/${typeInfo.channel_type}`)
        const data = await resp.json() as QrState
        setQrState(data)
        if (data.status === "confirmed") {
          stopQrPolling()
          setTimeout(() => onClose(), 1500)
        } else if (data.status === "expired" || data.status === "timeout") {
          stopQrPolling()
          setError(data.status === "expired" ? "二维码已过期，请重试" : "二维码已超时，请重试")
        }
      } catch {
        // ignore poll errors
      }
    }
    poll()
    qrTimerRef.current = setInterval(poll, 2000)
  }

  const handleSaveAndConnect = async () => {
    setError("")
    setSaving(true)
    try {
      await onSave(typeInfo.channel_type, config)
    } catch (e: any) {
      setError(e?.message || "保存失败")
      setSaving(false)
      return
    }
    setSaving(false)

    if (typeInfo.config_fields.length === 0) {
      // Weixin: save config then directly connect + show QR
      setConnecting(true)
      try {
        await onConnect(typeInfo.channel_type)
        startQrPolling()
      } catch (e: any) {
        setError(e?.message || "连接失败")
      }
      setConnecting(false)
      return
    }

    setConnecting(true)
    try {
      await onConnect(typeInfo.channel_type)
    } catch (e: any) {
      setError(e?.message || "连接失败")
    }
    setConnecting(false)
  }

  const handleConnect = async () => {
    setError("")
    setConnecting(true)
    try {
      await onConnect(typeInfo.channel_type)
      if (typeInfo.channel_type === "weixin") {
        startQrPolling()
      }
    } catch (e: any) {
      setError(e?.message || "连接失败")
    }
    setConnecting(false)
  }

  const handleDisconnect = async () => {
    setError("")
    setDisconnecting(true)
    try {
      await onDisconnect(typeInfo.channel_type)
      stopQrPolling()
      setQrState(null)
    } catch (e: any) {
      setError(e?.message || "断开失败")
    }
    setDisconnecting(false)
  }

  if (!open) return null

  const hasConfigFields = typeInfo.config_fields.length > 0

  return (
    <div className="fixed inset-0 z-[60]" onClick={onClose}>
      <div
        className="absolute right-0 top-0 h-full w-[380px] max-w-[90vw] bg-card border-l border-border shadow-2xl overflow-auto animate-in"
        style={{ animation: "slideInRight 0.2s ease-out both" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
          <div className="size-8 flex items-center justify-center text-foreground">
            {IconComp && <IconComp size={24} />}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-foreground">{typeInfo.display_name}</h3>
            <p className="text-[10px] text-muted-foreground">{typeInfo.english_name}</p>
          </div>
          <button onClick={() => { stopQrPolling(); onClose() }} className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
            <X className="size-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Description */}
          <p className="text-xs text-muted-foreground">{typeInfo.description}</p>

          {/* Capability tags */}
          <div className="flex flex-wrap gap-1.5">
            {typeInfo.capabilities.send.map(k => (
              <span key={k} className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700">
                {CAP_LABELS[k] || k}
              </span>
            ))}
          </div>

          {/* QR Code display */}
          {qrState && (
            <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border p-4">
              <QrCode className="size-6 text-foreground" />
              {qrState.qrcode_url ? (
                (() => {
                  const raw = qrState.qrcode_url
                  let src: string
                  // Direct image formats
                  if (raw.startsWith("data:image/")) {
                    src = raw
                  } else if (/\.(png|jpg|jpeg|gif|svg|webp)(\?|$)/i.test(raw)) {
                    src = raw
                  } else if (raw.length > 200 && !raw.startsWith("http")) {
                    // Raw base64, prepend data URI
                    src = `data:image/png;base64,${raw}`
                  } else {
                    // URL, ID, or short string — generate QR code via external API
                    src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(raw)}`
                  }
                  return (
                    <>
                      <img src={src} alt="登录二维码" className="w-48 h-48 rounded-lg border border-border"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; setError("无法加载二维码，请重试") }} />
                      <p className="text-xs text-muted-foreground">请使用微信扫描二维码</p>
                    </>
                  )
                })()
              ) : (
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
              )}
              <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${
                qrState.status === "confirmed" ? "bg-green-100 text-green-700" :
                qrState.status === "expired" || qrState.status === "timeout" ? "bg-red-100 text-red-700" :
                "bg-blue-100 text-blue-700"
              }`}>
                {qrPolling && qrState.status !== "confirmed" && <Loader2 className="size-3 animate-spin inline mr-1.5" />}
                {QR_STATUS_LABELS[qrState.status] || qrState.status}
              </span>
              {(qrState.status === "expired" || qrState.status === "timeout") && (
                <button onClick={() => { setQrState(null); setError(""); handleConnect() }}
                  className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent transition-colors">
                  重新扫码
                </button>
              )}
            </div>
          )}

          {/* Status bar */}
          {status === "connecting" && !qrState && (
            <div className="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-xs">
              <Loader2 className="size-2 animate-spin text-blue-500" />
              <span className="font-semibold text-blue-700">连接中...</span>
            </div>
          )}
          {status === "connected" && !qrState && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-xs">
              <Circle className="size-2 text-green-500 fill-green-500" />
              <span className="font-semibold text-green-700">已连接</span>
              {mainInfo?.connected_since && (
                <span className="text-green-600/70">· {mainInfo.message_count} 条消息</span>
              )}
            </div>
          )}
          {status === "configured" && !qrState && (
            <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs">
              <Circle className="size-2 text-amber-500 fill-amber-500" />
              <span className="font-semibold text-amber-700">凭证已保存，等待连接</span>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-[11px] text-red-700">
              {error}
            </div>
          )}

          {/* Config form */}
          {hasConfigFields && !qrState && (
            <div>
              <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-3">配置</div>
              {typeInfo.config_fields.map(f => (
                <FieldInput
                  key={f.key}
                  field={f}
                  value={config[f.key] ?? ""}
                  onChange={v => setConfig(prev => ({ ...prev, [f.key]: v }))}
                />
              ))}
            </div>
          )}

          {/* Notes */}
          {typeInfo.notes && !qrState && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-700">
              {typeInfo.notes}
            </div>
          )}

          {/* Action buttons */}
          {!qrState && (
            <div className="space-y-2 pt-2">
              {status === "unconfigured" && (
                <button
                  onClick={handleSaveAndConnect}
                  disabled={saving || connecting}
                  className="w-full rounded-lg bg-indigo-600 text-white px-4 py-2.5 text-xs font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {(saving || connecting) && <Loader2 className="size-3 animate-spin" />}
                  {saving ? "保存中..." : connecting ? "连接中..." : "保存并连接"}
                </button>
              )}

              {status === "configured" && (
                <div className="space-y-2">
                  <button
                    onClick={handleConnect}
                    disabled={connecting}
                    className="w-full rounded-lg bg-green-600 text-white px-4 py-2.5 text-xs font-semibold hover:bg-green-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {connecting && <Loader2 className="size-3 animate-spin" />}
                    {typeInfo.channel_type === "weixin" ? "扫码连接" : "连接"}
                  </button>
                  <button
                    onClick={handleDisconnect}
                    disabled={disconnecting}
                    className="w-full rounded-lg border border-red-300 text-red-600 bg-white px-4 py-2.5 text-xs font-semibold hover:bg-red-50 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {disconnecting && <Loader2 className="size-3 animate-spin" />}
                    重置并清除凭证
                  </button>
                </div>
              )}

              {status === "connected" && (
                <div className="space-y-2">
                  <button
                    onClick={handleDisconnect}
                    disabled={disconnecting}
                    className="w-full rounded-lg border border-red-300 text-red-600 bg-white px-4 py-2.5 text-xs font-semibold hover:bg-red-50 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {disconnecting && <Loader2 className="size-3 animate-spin" />}
                    断开连接
                  </button>
                  {hasConfigFields && (
                    <button
                      onClick={handleSaveAndConnect}
                      disabled={saving}
                      className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-xs hover:bg-accent transition-colors flex items-center justify-center gap-2"
                    >
                      {saving && <Loader2 className="size-3 animate-spin" />}
                      更新凭证
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
