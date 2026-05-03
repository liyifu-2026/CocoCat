import { useState } from "react"
import type { EntryConfig, ChannelInfo } from "@/api/entries"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Plus, Trash2 } from "lucide-react"

interface EntryManagerProps {
  title: string
  entries: EntryConfig[] | undefined
  allChannels: ChannelInfo[] | undefined
  onSave: (entries: EntryConfig[]) => Promise<void>
}

export function EntryManager({ title, entries, allChannels, onSave }: EntryManagerProps) {
  const [editing, setEditing] = useState(false)
  const [localEntries, setLocalEntries] = useState<EntryConfig[]>([])
  const [selectedChannel, setSelectedChannel] = useState("")

  function startEdit() {
    setLocalEntries(entries ? entries.map(e => ({ ...e, config: { ...e.config } })) : [])
    setEditing(true)
  }

  function addEntry() {
    if (!selectedChannel) return
    const ch = allChannels?.find(c => c.id === selectedChannel)
    if (!ch) return
    const defaults: Record<string, string> = {}
    for (const [k, v] of Object.entries(ch.config_schema)) {
      defaults[k] = (v as { default: string }).default ?? ""
    }
    setLocalEntries(prev => [...prev, { channel: selectedChannel, config: defaults, enabled: true }])
    setSelectedChannel("")
  }

  function removeEntry(i: number) {
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

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        {editing ? (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
            <Button size="sm" onClick={save}>Save</Button>
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
                      <Switch checked={entry.enabled} onCheckedChange={() => toggleEnabled(i)} />
                    </div>
                    <button onClick={() => removeEntry(i)} className="text-destructive hover:text-destructive/80">
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                  {ch && Object.entries(ch.config_schema).map(([key, schema]) => (
                    <div key={key}>
                      <label className="text-xs text-muted-foreground">{key}</label>
                      <Input size={1}
                        value={entry.config[key] ?? ""}
                        onChange={e => updateConfig(i, key, e.target.value)}
                        placeholder={(schema as { description: string }).description}
                        className="mt-0.5"
                      />
                    </div>
                  ))}
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
  )
}
