import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { PlatformGrid } from "./PlatformGrid"
import { ChannelDrawer } from "./ChannelDrawer"

const API_BASE = "/api/channels"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function ChannelsTab() {
  const [types, setTypes] = useState<ChannelTypeInfo[]>([])
  const [mainChannels, setMainChannels] = useState<MainChannelInfo[]>([])
  const [typesLoading, setTypesLoading] = useState(true)
  const [typesError, setTypesError] = useState("")
  const [mainLoading, setMainLoading] = useState(true)
  const [mainError, setMainError] = useState("")

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedType, setSelectedType] = useState<ChannelTypeInfo | null>(null)
  const [selectedMain, setSelectedMain] = useState<MainChannelInfo | undefined>(undefined)

  const loadTypes = useCallback(async () => {
    setTypesLoading(true)
    setTypesError("")
    try {
      const data = await fetchJSON<{ types: ChannelTypeInfo[] }>(`${API_BASE}/types`)
      setTypes(data.types)
    } catch (e: any) {
      setTypesError(e?.message || "加载渠道类型失败")
    } finally {
      setTypesLoading(false)
    }
  }, [])

  const loadMain = useCallback(async () => {
    setMainLoading(true)
    setMainError("")
    try {
      const data = await fetchJSON<{ channels: MainChannelInfo[] }>(`${API_BASE}/main`)
      setMainChannels(data.channels)
    } catch (e: any) {
      setMainError(e?.message || "加载 Main AI 渠道状态失败")
    } finally {
      setMainLoading(false)
    }
  }, [])

  // Fetch on mount
  useEffect(() => { loadTypes(); loadMain() }, [loadTypes, loadMain])

  const handleCardClick = (typeInfo: ChannelTypeInfo, mainInfo?: MainChannelInfo) => {
    setSelectedType(typeInfo)
    setSelectedMain(mainInfo)
    setDrawerOpen(true)
  }

  const handleClose = () => {
    setDrawerOpen(false)
    setSelectedType(null)
    setSelectedMain(undefined)
  }

  const handleSave = async (channelType: string, config: Record<string, string>) => {
    await fetchJSON(`${API_BASE}/main/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_type: channelType, config }),
    })
    toast.success("配置已保存")
    await loadMain()
  }

  const handleConnect = async (channelType: string) => {
    try {
      await fetchJSON(`${API_BASE}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_type: "main", target_id: "main", channel_type: channelType }),
      })
      toast.success(`${channelType} 已连接`)
      await loadMain()
    } catch {
      throw new Error("连接失败")
    }
  }

  const handleDisconnect = async (channelType: string) => {
    try {
      await fetchJSON(`${API_BASE}/disconnect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_type: "main", target_id: "main", channel_type: channelType }),
      })
      toast.success(`${channelType} 已断开`)
      await loadMain()
    } catch {
      throw new Error("断开失败")
    }
  }

  const loading = typesLoading || mainLoading
  const error = typesError || mainError

  return (
    <div className="space-y-4">
      <PlatformGrid
        typeInfos={types}
        mainChannels={mainChannels}
        onCardClick={handleCardClick}
        loading={loading}
        error={error}
        onRetry={() => { loadTypes(); loadMain() }}
      />

      {selectedType && (
        <ChannelDrawer
          open={drawerOpen}
          onClose={handleClose}
          typeInfo={selectedType}
          mainInfo={selectedMain}
          onSave={handleSave}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      )}
    </div>
  )
}
