import type { LucideIcon } from "lucide-react"

export interface TabItem { label: string; icon: LucideIcon }

export interface ProviderInfo {
  name: string
  display_name: string
  base_url: string
  env_key: string
  has_key: boolean
  connected: boolean
  custom: boolean
  enabled_count: number
  keywords: string[]
}

// ── Channel types ──

export interface ChannelConfigField {
  key: string
  label: string
  required: boolean
  type: "text" | "password"
  placeholder: string
}

export interface ChannelCapabilities {
  receive: string[]
  send: string[]
  streaming: boolean
  cards: boolean
  reactions: boolean
  threads: boolean
}

export interface ChannelTypeInfo {
  channel_type: string
  display_name: string
  english_name: string
  description: string
  capabilities: ChannelCapabilities
  config_fields: ChannelConfigField[]
  notes: string | null
  icon_type: "simple" | "hand"
}

export interface ChannelTypeListResponse {
  types: ChannelTypeInfo[]
}

export interface MainChannelInfo {
  channel_type: string
  display_name: string
  enabled: boolean
  status: "connected" | "configured" | "unconfigured"
  connected_since: string | null
  message_count: number
}

export interface MainChannelListResponse {
  channels: MainChannelInfo[]
}

// ── Tab data ──

export interface TabData {
  agents?: { id: string; name: string; role: string; model: string; status: string }[]
  providers?: ProviderInfo[]
  scenes?: { id: string; name?: string; kbs?: string[]; skills?: string[] }[]
  global?: { name: string; description: string }[]
  kbs?: { id: string; purpose?: string }[]
  channels?: { channel_type: string; target_type: string; target_id: string; status: string }[]
}

export interface SettingsModalProps {
  open: boolean
  onClose: () => void
}
