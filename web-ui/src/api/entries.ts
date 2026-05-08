import { api } from "./client"

export interface ConfigField {
  key: string
  label: string
  type: "text" | "secret" | "number"
  default?: string
}

export interface ChannelInfo {
  id: string
  name: string
  description: string
  config_fields: ConfigField[]
  needs_qr_login?: boolean
}

export interface EntryConfig {
  channel: string
  config: Record<string, string>
  enabled: boolean
}

export interface ChannelStatus {
  status: string
  channel_type: string
  connected: boolean
}

export interface QrCodeData {
  qrcode_url: string
  qrcode: string
}

export const entriesApi = {
  listChannels: () => api.get<{ channels: ChannelInfo[] }>("/channels"),

  // Agent entries
  getAgentEntries: (agentId: string) =>
    api.get<{ entries: EntryConfig[] }>(`/agents/${agentId}/entries`),
  updateAgentEntries: (agentId: string, entries: EntryConfig[]) =>
    api.put<{ entries: EntryConfig[] }>(`/agents/${agentId}/entries`, { entries }),

  // Scene entries
  getSceneEntries: (sceneId: string) =>
    api.get<{ entries: EntryConfig[] }>(`/scenes/${sceneId}/entries`),
  updateSceneEntries: (sceneId: string, entries: EntryConfig[]) =>
    api.put<{ entries: EntryConfig[] }>(`/scenes/${sceneId}/entries`, { entries }),

  // Channel connect/disconnect
  connectChannel: (targetType: string, targetId: string, channelType: string, config: Record<string, string>) =>
    api.post<{ status: string }>("/channels/connect", { target_type: targetType, target_id: targetId, channel_type: channelType, config }),
  disconnectChannel: (targetType: string, targetId: string, channelType: string) =>
    api.post<{ status: string }>("/channels/disconnect", { target_type: targetType, target_id: targetId, channel_type: channelType, config: {} }),

  // Status
  getChannelStatus: (targetType: string, targetId: string, channelType: string) =>
    api.get<ChannelStatus>(`/channels/${targetType}/${targetId}/${channelType}/status`),

  // WeChat QR
  getWeixinQr: () =>
    api.get<{ qrcode_url: string; qrcode: string; status: string }>("/channels/weixin/qr"),
  getWeixinQrStatus: () =>
    api.get<{ status: string; connected: boolean }>("/channels/weixin/qr/status"),
}
