# Channel Settings Frontend & API Design

## Date: 2026-05-16

## Overview

Redesign the "渠道" (Channels) tab in Settings to manage Main AI bot channels with full lifecycle: browse supported platforms, configure credentials, connect/disconnect, and monitor real-time status. Per-scene channel management is handled separately in scene settings.

## Scope

- **In scope**: Main AI channel management (view types, configure credentials, connect/disconnect, real-time status display)
- **Out of scope**: Per-scene channel management (handled in scene settings), custom/third-party channel type registration, channel config import/export

## Backend

### New Endpoints

All under `/api/channels` prefix:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/types` | GET | Return channel type metadata for all supported platforms |
| `/main` | GET | List Main AI configured channels with runtime status |
| `/main/config` | POST | Write/update a channel's config in `main.yaml` |
| `/connect` | POST | Start a channel (existing, extend for `target_type: "main"`) |
| `/disconnect` | POST | Stop a channel (existing) |

Persistence via `main.yaml` in the project root or config directory.

### main.yaml format

```yaml
# Main AI channel configuration
channels:
  feishu:
    enabled: true
    config:
      app_id: "cli_xxx"
      app_secret: "..."
  wechat:
    enabled: false
    config: {}
  weixin:
    enabled: false
    config: {}
  telegram:
    enabled: false
    config: {}
  discord:
    enabled: false
    config: {}
  web_api:
    enabled: false
    config: {}
```

### API Response Shapes

**`GET /api/channels/types`** (static, no persistence needed):
```json
{
  "types": [
    {
      "channel_type": "feishu",
      "display_name": "飞书",
      "english_name": "Feishu / Lark",
      "description": "...",
      "capabilities": {
        "receive": ["text", "image", "voice", "file", "video", "sticker", "link", "post"],
        "send": ["text", "post", "card", "image", "voice", "file", "video"],
        "streaming": true,
        "cards": true,
        "reactions": true,
        "threads": true
      },
      "config_fields": [
        {"key": "app_id", "label": "App ID", "required": true, "type": "text"},
        {"key": "app_secret", "label": "App Secret", "required": true, "type": "password"}
      ],
      "notes": null
    }
    // ... wechat, weixin, telegram, discord, web_api
  ]
}
```

**`GET /api/channels/main`**:
```json
{
  "channels": [
    {
      "channel_type": "feishu",
      "display_name": "飞书",
      "enabled": true,
      "status": "connected",
      "connected_since": "2026-05-16T14:32:00Z",
      "message_count": 1247
    }
  ]
}
```

**`POST /api/channels/main/config`**:
```json
// Request
{
  "channel_type": "feishu",
  "config": {
    "app_id": "cli_xxx",
    "app_secret": "..."
  }
}
// Response
{"status": "ok"}
```

## Frontend

### Tech Stack
- React 19 + TypeScript
- Tailwind CSS v4 (design tokens via CSS custom properties)
- Simple Icons via `@iconify/react` (pre-integrated in `provider-icons.tsx`)
- Lucide React (UI icons)
- Radix UI primitives
- `@tanstack/react-query` for server state

### Component Tree

```
ChannelsTab
├── PlatformGrid              ← 3-column responsive grid
│   ├── ChannelCard × 6      ← logo + name + capability tags + status pill
│   │   └── onClick → open ChannelDrawer
│   └── Empty state          ← if no types loaded
│
└── ChannelDrawer             ← Sheet/Dialog, slides from right
    ├── Header               ← channel logo + name + close button
    ├── CapabilityTags       ← chips for receive/send types
    ├── StatusBar            ← connected(绿)/configured(黄)/unconfigured(灰)
    ├── ConfigForm           ← dynamic fields from config_fields metadata
    ├── ActionButtons        ← save+connect / disconnect / qr-login
    └── ConnectionInfo       ← uptime, message count (only when connected)
```

### Channel Card States

| State | Border/Style | Status Pill |
|-------|-------------|-------------|
| Connected | Green border, subtle green bg | "已连接" green dot |
| Configured (not connected) | Yellow border, subtle yellow bg | "已配置" yellow dot |
| Unconfigured | Gray border, muted | "未配置" gray dot |

### Channel Drawer States

**State: Unconfigured**
- Empty config form fields
- "保存并连接" primary button
- Platform-specific notes (e.g., "需要公网 IP" for WeChat)

**State: Configured, Not Connected**
- Pre-filled readonly config fields (masked secrets)
- "连接" or "扫码连接" (for iLink) primary button
- "重置" secondary button

**State: Connected**
- Green status bar with uptime
- Pre-filled readonly config fields (masked secrets)
- "更新凭证" secondary button
- "断开连接" danger button
- Connection info footer (last connected, message count)

### QR Login Flow (iLink / 个人微信)

For channels that require QR code scanning, the drawer shows a QR code image placeholder. The frontend polls a status endpoint (e.g., `GET /api/channels/status?channel_type=weixin`) until the QR scan is confirmed, then transitions to the connected state.

### Channel Types (Hardcoded List, 6 platforms)

| channel_type | Display | English | Icon Source | Config Fields |
|-------------|---------|---------|-------------|---------------|
| `feishu` | 飞书 | Feishu / Lark | Hand-drawn SVG | app_id (req), app_secret (req) |
| `wechat` | 微信公众 | WeChat Official | simple-icons:wechat | app_id (req), token (req), encoding_aes_key (opt) |
| `weixin` | 个人微信 | iLink Bot | Hand-drawn SVG | none (QR login) |
| `telegram` | Telegram | Telegram Bot | simple-icons:telegram | bot_token (req) |
| `discord` | Discord | Discord Bot | simple-icons:discord | bot_token (req) |
| `web_api` | Web API | HTTP REST | Hand-drawn SVG | endpoint (req), api_key (opt) |

Simple Icons logos sourced from `@iconify-json/simple-icons` (same pattern as `lib/provider-icons.tsx`). Missing logos (feishu, weixin, web_api) use hand-drawn inline SVGs following the existing `HandIcon` pattern.

### Capability Tag Icons

Mapping of capability features to short Chinese labels:
- text → "文字", image → "图片", voice → "语音", file → "文件", video → "视频"
- card → "卡片", streaming → "流式", threads → "多线程", reactions → "反馈"

### Icons Used (Lucide)

- Tab icon: Radio (existing, unchanged)
- Channel cards: platform brand logos
- Capability tag icons: Lucide inline where relevant
- Status indicators: colored `Circle` from Lucide
- QR: `QrCode` from Lucide
- Eye toggle: `Eye` / `EyeOff` from Lucide (already used in ProvidersTab)

### Data Flow

```
1. ChannelsTab mounts
   → useQuery GET /api/channels/types  (cached, rarely changes)
   → useQuery GET /api/channels/main   (refetches on window focus)

2. User clicks unconfigured card → ChannelDrawer opens
   → Form fields rendered from type.capabilities.config_fields
   → User fills fields → POST /api/channels/main/config
   → On success: POST /api/channels/connect (target_type="main")
   → On success: invalidate main channel query → card turns green

3. User clicks connected card → ChannelDrawer opens
   → Shows status + readonly config
   → User clicks "断开" → POST /api/channels/disconnect
   → On success: invalidate query → card turns yellow/gray

4. User clicks configured (not connected) card → ChannelDrawer opens
   → Shows status + readonly config
   → User clicks "连接" → POST /api/channels/connect
   → On success: invalidate query → card turns green
```

### Error Handling

- Network errors: toast notification via `sonner`
- Config validation: inline field errors (red border + message below field)
- Connection failure: drawer shows error message in status bar
- QR login timeout: drawer updates with "已过期" and retry button

### Empty / Edge States

- All channels unconfigured: grid shows all 6 cards in gray state
- API "/types" fails: show ErrorState component with retry button (existing pattern)
- API "/main" fails: show toast, cards fall back to unconfigured state
- Disconnect failure: keep card green, show error toast

### Responsive

- 3 columns on desktop (wider than 768px)
- 2 columns on tablet
- Drawer becomes full-screen on mobile (follows existing Sheet/Dialog responsive pattern)

## Constraints

- No custom channel type registration — 6 supported types are fixed
- Channel type metadata sourced from backend `/api/channels/types`, not hardcoded in frontend (except logo mapping)
- Config persistence relies on `main.yaml` file I/O on the server
- QR login status polling interval: 2s, timeout: 180s (matches existing iLink wait loop)
