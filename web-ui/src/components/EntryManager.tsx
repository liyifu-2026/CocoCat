import { useState, useEffect, useCallback } from "react"
import type { EntryConfig, ChannelInfo, ChannelStatus } from "@/api/entries"
import { entriesApi } from "@/api/entries"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { Plus, Trash2, Plug, Unplug, QrCode, Loader2 } from "lucide-react"

interface EntryManagerProps {
  title: string
  targetType: "scene" | "agent"
  targetId: string
  entries: EntryConfig[] | undefined
  allChannels: ChannelInfo[] | undefined
  onSave: (entries: EntryConfig[]) => Promise<void>
}

type ConnectionState = "disconnected" | "connecting" | "connected" | "error"

export function EntryManager({ title, targetType, targetId, entries, allChannels, onSave }: EntryManagerProps) {
  const [editing, setEditing] = useState(false)
  const [localEntries, setLocalEntries] = useState<EntryConfig[]>([])
  const [selectedChannel, setSelectedChannel] = useState("")
  const [statusMap, setStatusMap] = useState<Record<string, ConnectionState>>({})
  const [qrDialogOpen, setQrDialogOpen] = useState(false)
  const [qrData, setQrData] = useState({ qrcode_url: "", channelId: "" })
  const [qrPolling, setQrPolling] = useState(false)
  const [connecting, setConnecting] = useState<string | null>(null)

  function startEdit() {
    setLocalEntries(entries ? entries.map(e => ({ ...e, config: { ...e.config } })) : [])
    setEditing(true)
    // Fetch status for all entries
    if (entries) {
      for (const e of entries) {
        fetchStatus(e.channel)
      }
    }
  }

  async function fetchStatus(channelType: string) {
    try {
      const res = await entriesApi.getChannelStatus(targetType, targetId, channelType)
      setStatusMap(prev => ({ ...prev, [channelType]: res.connected ? "connected" : "disconnected" }))
    } catch {
      setStatusMap(prev => ({ ...prev, [channelType]: "disconnected" }))
    }
  }

  async function handleConnect(entry: EntryConfig, ch: ChannelInfo) {
    setConnecting(entry.channel)
    setStatusMap(prev => ({ ...prev, [entry.channel]: "connecting" }))
    try {
      if (ch.needs_qr_login) {
        // Start channel immediately (it will begin QR login in background thread)
        entriesApi.connectChannel(targetType, targetId, entry.channel, entry.config).catch(() => {})

        // Poll for QR state from the channel
        const pollQr = async () => {
          try {
            const qrStatus = await entriesApi.getWeixinQrStatus()
            if (qrStatus.connected) {
              setQrDialogOpen(false)
              setQrPolling(false)
              setStatusMap(prev => ({ ...prev, [entry.channel]: "connected" }))
              return false
            }
            if (qrStatus.status === "waiting" || qrStatus.status === "scanned") {
              if (!qrDialogOpen) {
                const qr = await entriesApi.getWeixinQr()
                if (qr.qrcode_url) {
                  setQrData({ qrcode_url: qr.qrcode_url, channelId: entry.channel })
                  setQrDialogOpen(true)
                  setQrPolling(true)
                }
              }
              return true
            }
            // Also check actual channel status as fallback (credentials may already exist)
            if (qrStatus.status === "idle") {
              const chStatus = await entriesApi.getChannelStatus(targetType, targetId, entry.channel)
              if (chStatus.connected) {
                setQrDialogOpen(false)
                setQrPolling(false)
                setStatusMap(prev => ({ ...prev, [entry.channel]: "connected" }))
                return false
              }
            }
            if (qrStatus.status === "expired" || qrStatus.status === "timeout" || qrStatus.status === "failed") {
              setQrDialogOpen(false)
              setQrPolling(false)
              setStatusMap(prev => ({ ...prev, [entry.channel]: "error" }))
              return false
            }
            return true
          } catch { return true }
        }

        let polling = true
        while (polling) {
          await new Promise(r => setTimeout(r, 2000))
          polling = await pollQr()
        }
        setConnecting(null)
        return
      }
      await entriesApi.connectChannel(targetType, targetId, entry.channel, entry.config)
      setStatusMap(prev => ({ ...prev, [entry.channel]: "connected" }))
    } catch {
      setStatusMap(prev => ({ ...prev, [entry.channel]: "error" }))
    }
    setConnecting(null)
  }

  async function handleDisconnect(channelType: string) {
    try {
      await entriesApi.disconnectChannel(targetType, targetId, channelType)
      setStatusMap(prev => ({ ...prev, [channelType]: "disconnected" }))
    } catch {
      // ignore
    }
  }

  function addEntry() {
    if (!selectedChannel) return
    const ch = allChannels?.find(c => c.id === selectedChannel)
    if (!ch) return
    const defaults: Record<string, string> = {}
    for (const field of ch.config_fields ?? []) {
      defaults[field.key] = field.default ?? ""
    }
    setLocalEntries(prev => [...prev, { channel: selectedChannel, config: defaults, enabled: true }])
    setSelectedChannel("")
  }

  function removeEntry(i: number) {
    const entry = localEntries[i]
    if (entry && statusMap[entry.channel] === "connected") {
      handleDisconnect(entry.channel)
    }
    setLocalEntries(prev => prev.filter((_, j) => j !== i))
  }

  function updateConfig(i: number, key: string, value: string) {
    setLocalEntries(prev => prev.map((e, j) => j === i ? { ...e, config: { ...e.config, [key]: value } } : e))
  }

  function toggleEnabled(i: number) {
    setLocalEntries(prev => prev.map((e, j) => j === i ? { ...e, enabled: !e.enabled } : e))
  }

  async function save() {
    await onSave(localEntries)
    setEditing(false)
  }

  const usedChannels = new Set(localEntries.map(e => e.channel))
  const availableChannels = allChannels?.filter(c => !usedChannels.has(c.id)) ?? []

  function statusBadge(channelType: string) {
    const s = statusMap[channelType]
    if (!s) return null
    const colors: Record<string, string> = {
      connected: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
      disconnected: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
      connecting: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
      error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    }
    return <span className={`text-xs px-1.5 py-0.5 rounded ${colors[s] ?? ""}`}>{s}</span>
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {editing ? (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
              <Button size="sm" onClick={save}>Save Config</Button>
            </div>
          ) : (
            <Button size="sm" variant="outline" onClick={startEdit}>Edit</Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {localEntries.length === 0 && !editing && (
            <p className="text-sm text-muted-foreground">No entries configured</p>
          )}

          {editing ? (
            <>
              {localEntries.map((entry, i) => {
                const ch = allChannels?.find(c => c.id === entry.channel)
                return (
                  <div key={i} className="rounded-lg border border-border p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{ch?.name ?? entry.channel}</Badge>
                        {statusBadge(entry.channel)}
                        <Switch checked={entry.enabled} onCheckedChange={() => toggleEnabled(i)} />
                      </div>
                      <div className="flex items-center gap-1">
                        {statusMap[entry.channel] === "connected" ? (
                          <Button size="xs" variant="outline"
                            onClick={() => handleDisconnect(entry.channel)}
                            title="Disconnect">
                            <Unplug className="size-3" />
                          </Button>
                        ) : (
                          <Button size="xs" variant="outline"
                            onClick={() => ch && handleConnect(entry, ch)}
                            disabled={connecting === entry.channel}
                            title="Connect">
                            {connecting === entry.channel
                              ? <Loader2 className="size-3 animate-spin" />
                              : <Plug className="size-3" />
                            }
                          </Button>
                        )}
                        <button onClick={() => removeEntry(i)} className="text-destructive hover:text-destructive/80">
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    </div>
                    {ch && (ch.config_fields ?? []).map(field => (
                      <div key={field.key}>
                        <label className="text-xs text-muted-foreground">{field.label}</label>
                        <Input size={1}
                          type={field.type === "secret" ? "password" : "text"}
                          value={entry.config[field.key] ?? ""}
                          onChange={e => updateConfig(i, field.key, e.target.value)}
                          className="mt-0.5"
                        />
                      </div>
                    ))}
                    {ch?.needs_qr_login && (
                      <p className="text-xs text-muted-foreground">Click connect to scan QR code with WeChat</p>
                    )}
                  </div>
                )
              })}
              {availableChannels.length > 0 && (
                <div className="flex gap-2">
                  <Select value={selectedChannel} onValueChange={setSelectedChannel}>
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Add channel..." />
                    </SelectTrigger>
                    <SelectContent>
                      {availableChannels.map(ch => (
                        <SelectItem key={ch.id} value={ch.id}>{ch.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button size="sm" variant="outline" onClick={addEntry} disabled={!selectedChannel}>
                    <Plus className="size-4" />
                  </Button>
                </div>
              )}
            </>
          ) : (
            entries?.map((entry, i) => {
              const ch = allChannels?.find(c => c.id === entry.channel)
              return (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant={entry.enabled ? "default" : "secondary"}>{ch?.name ?? entry.channel}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {Object.entries(entry.config).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join(", ")}
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      {/* WeChat QR dialog */}
      <Dialog open={qrDialogOpen} onOpenChange={(open) => { if (!open) { setQrDialogOpen(false); setQrPolling(false) }}}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Connect WeChat</DialogTitle>
            <DialogDescription>Scan the QR code with your WeChat app to login</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            {qrData.qrcode_url ? (
              <div className="border border-border rounded-lg p-2">
                <img src={qrData.qrcode_url} alt="WeChat QR code" className="w-48 h-48" />
              </div>
            ) : (
              <div className="w-48 h-48 flex items-center justify-center bg-muted rounded-lg">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
              </div>
            )}
            {qrPolling && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Waiting for scan...
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
