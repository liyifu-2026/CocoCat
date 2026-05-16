# Channel Settings Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the read-only ChannelsTab with a full-featured Main AI channel management UI (platform grid + config drawer), backed by new API endpoints for channel types, main channel config persistence, and connect/disconnect.

**Architecture:** New backend endpoints (`/api/channels/types`, `/api/channels/main`, `/api/channels/main/config`) serve channel metadata and persist config to `config/main.yaml`. Frontend uses a 3-column platform grid with clicked-to-open config drawer pattern. Channel logos use Simple Icons (telegram, wechat, discord) with hand-drawn SVG fallbacks (feishu, weixin, web_api).

**Tech Stack:** Python FastAPI (backend), React 19 + TypeScript + Tailwind CSS v4 (frontend), @iconify/react for brand icons, lucide-react for UI icons, sonner for toasts.

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `cococat/routes/channels.py` | Modify | Add `/types`, `/main`, `/main/config` endpoints |
| `config/main.yaml` | Create | Main AI channel config persistence |
| `web-ui/src/types/settings.ts` | Modify | Add channel type definitions |
| `web-ui/src/lib/channel-icons.tsx` | Create | Channel platform logo components |
| `web-ui/src/components/settings/ChannelsTab.tsx` | Rewrite | New full-featured tab |
| `web-ui/src/components/SettingsModal.tsx` | Modify | Wire new ChannelsTab with fetch hooks |

---

### Task 1: Channel Types Metadata Endpoint

**Files:**
- Modify: `cococat/routes/channels.py`

- [ ] **Step 1: Add `/api/channels/types` endpoint**

Add to `cococat/routes/channels.py`, after the `CHANNEL_STATUS` dict (line 39):

```python
# ── Channel type metadata (static) ──

CHANNEL_TYPES = [
    {
        "channel_type": "feishu",
        "display_name": "飞书",
        "english_name": "Feishu / Lark",
        "description": "飞书机器人，支持富文本卡片、流式输出、多线程对话",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker", "link", "post"],
            "send": ["text", "card", "image", "voice", "file", "video"],
            "streaming": True,
            "cards": True,
            "reactions": True,
            "threads": True,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "cli_a6b..."},
            {"key": "app_secret", "label": "App Secret", "required": True, "type": "password", "placeholder": ""},
        ],
        "notes": None,
        "icon_type": "hand",
    },
    {
        "channel_type": "wechat",
        "display_name": "微信公众",
        "english_name": "WeChat Official",
        "description": "微信公众号，通过被动回复 XML 消息与用户交互",
        "capabilities": {
            "receive": ["text", "image", "voice", "location", "link", "event"],
            "send": ["text", "image", "voice", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "wxXXXXXXXXXXXXXXXX"},
            {"key": "token", "label": "Token", "required": True, "type": "text", "placeholder": "从微信后台获取"},
            {"key": "encoding_aes_key", "label": "Encoding AES Key", "required": False, "type": "text", "placeholder": "消息加解密密钥（可选）"},
        ],
        "notes": "需要公网 IP 和已备案域名以接收微信回调",
        "icon_type": "simple",
    },
    {
        "channel_type": "weixin",
        "display_name": "个人微信",
        "english_name": "iLink Bot",
        "description": "个人微信机器人，通过 ilink 接口实现消息收发，扫码登录无需手动填配置",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [],
        "notes": "自动通过二维码扫码登录，无需手动填写凭证",
        "icon_type": "hand",
    },
    {
        "channel_type": "telegram",
        "display_name": "Telegram",
        "english_name": "Telegram Bot",
        "description": "Telegram Bot，通过 Bot API 收发消息，支持 Markdown 格式",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video"],
            "streaming": False,
            "cards": False,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 @BotFather 获取"},
        ],
        "notes": None,
        "icon_type": "simple",
    },
    {
        "channel_type": "discord",
        "display_name": "Discord",
        "english_name": "Discord Bot",
        "description": "Discord 机器人，支持频道消息收发和 Embed 卡片",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 Discord Developer Portal 获取"},
        ],
        "notes": None,
        "icon_type": "simple",
    },
    {
        "channel_type": "web_api",
        "display_name": "Web API",
        "english_name": "HTTP REST",
        "description": "通用 HTTP API 渠道，通过 REST 接口收发消息，可用于嵌入第三方应用",
        "capabilities": {
            "receive": ["text"],
            "send": ["text"],
            "streaming": False,
            "cards": False,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "endpoint", "label": "Endpoint URL", "required": True, "type": "text", "placeholder": "https://example.com/api/chat"},
            {"key": "api_key", "label": "API Key", "required": False, "type": "password", "placeholder": "可选认证密钥"},
        ],
        "notes": None,
        "icon_type": "hand",
    },
]


@router.get("/types")
async def list_channel_types():
    """Return metadata for all supported channel types."""
    return {"types": CHANNEL_TYPES}
```

- [ ] **Step 2: Run test to verify endpoint works**

```bash
cd /home/leaif/Project/CocoCat && python3 -c "
from cococat.routes.channels import CHANNEL_TYPES
assert len(CHANNEL_TYPES) == 6
for t in CHANNEL_TYPES:
    assert 'channel_type' in t
    assert 'display_name' in t
    assert 'config_fields' in t
    assert 'capabilities' in t
print('OK: 6 channel types defined')
"
```

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/channels.py
git commit -m "feat: add GET /api/channels/types endpoint with 6 channel metadata definitions"
```

---

### Task 2: Main YAML Config Management

**Files:**
- Create: `config/main.yaml` (initial template)
- Modify: `cococat/routes/channels.py`

- [ ] **Step 1: Create initial `config/main.yaml`**

Write to `config/main.yaml`:

```yaml
# Main AI channel configuration
channels:
  feishu:
    enabled: false
    config: {}
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

- [ ] **Step 2: Add helper functions to `cococat/routes/channels.py`**

Add after the `CHANNEL_TYPES` list (before the routes):

```python
import yaml

MAIN_CONFIG_PATH = os.path.join("config", "main.yaml")


def _load_main_config() -> dict:
    """Load main.yaml channel config."""
    if not os.path.exists(MAIN_CONFIG_PATH):
        return {"channels": {}}
    with open(MAIN_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"channels": {}}


def _save_main_config(data: dict):
    """Write main.yaml channel config."""
    os.makedirs(os.path.dirname(MAIN_CONFIG_PATH), exist_ok=True)
    with open(MAIN_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
```

- [ ] **Step 3: Run test to verify config read/write**

```bash
cd /home/leaif/Project/CocoCat && python3 -c "
import sys; sys.path.insert(0, '.')
from cococat.routes.channels import _load_main_config, _save_main_config
cfg = _load_main_config()
assert 'channels' in cfg
assert 'feishu' in cfg['channels']
_save_main_config(cfg)
cfg2 = _load_main_config()
assert cfg2 == cfg
print('OK: main.yaml read/write roundtrip')
"
```

- [ ] **Step 4: Commit**

```bash
git add config/main.yaml cococat/routes/channels.py
git commit -m "feat: add main.yaml config persistence with read/write helpers"
```

---

### Task 3: Main Channel List & Config Endpoints

**Files:**
- Modify: `cococat/routes/channels.py`

- [ ] **Step 1: Add `GET /api/channels/main` endpoint**

Add after the `/types` route in `cococat/routes/channels.py`:

```python
@router.get("/main")
async def list_main_channels():
    """List Main AI configured channels with runtime status."""
    cfg = _load_main_config()
    channels = cfg.get("channels", {})
    result = []

    for ct, info in channels.items():
        key = f"main:main:{ct}"
        status = CHANNEL_STATUS.get(key, {}).get("status", "stopped")
        # Resolve display name from channel types
        display_name = ct
        for t in CHANNEL_TYPES:
            if t["channel_type"] == ct:
                display_name = t["display_name"]
                break
        result.append({
            "channel_type": ct,
            "display_name": display_name,
            "enabled": info.get("enabled", False),
            "status": "connected" if status == "connected" else (
                "configured" if info.get("config") else "unconfigured"
            ),
            "connected_since": CHANNEL_STATUS.get(key, {}).get("connected_since"),
            "message_count": CHANNEL_STATUS.get(key, {}).get("message_count", 0),
        })

    return {"channels": result}
```

- [ ] **Step 2: Add `POST /api/channels/main/config` endpoint**

```python
class MainChannelConfig(BaseModel):
    channel_type: str
    config: dict = {}


@router.post("/main/config")
async def save_main_channel_config(body: MainChannelConfig):
    """Save or update a channel's configuration in main.yaml."""
    cfg = _load_main_config()
    channels = cfg.setdefault("channels", {})

    if body.channel_type not in channels:
        channels[body.channel_type] = {"enabled": False, "config": {}}

    channels[body.channel_type]["config"] = body.config
    channels[body.channel_type]["enabled"] = bool(body.config)

    _save_main_config(cfg)
    return {"status": "ok"}
```

- [ ] **Step 3: Run test to verify endpoints work**

```bash
cd /home/leaif/Project/CocoCat && python3 -c "
import sys; sys.path.insert(0, '.')
sys.path.insert(0, 'py-agent')
import asyncio
from cococat.routes.channels import (
    list_main_channels, save_main_channel_config,
    MainChannelConfig
)

async def test():
    # Test config save
    body = MainChannelConfig(channel_type='feishu', config={'app_id': 'test', 'app_secret': 'secret'})
    result = await save_main_channel_config(body)
    assert result['status'] == 'ok'

    # Test list
    result = await list_main_channels()
    channels = {c['channel_type']: c for c in result['channels']}
    assert channels['feishu']['status'] == 'configured'
    assert channels['wechat']['status'] == 'unconfigured'
    print('OK: main channel endpoints')

asyncio.run(test())
"
```

- [ ] **Step 4: Commit**

```bash
git add cococat/routes/channels.py
git commit -m "feat: add GET /api/channels/main and POST /api/channels/main/config endpoints"
```

---

### Task 4: Update Connect Endpoint for Main Target

**Files:**
- Modify: `cococat/routes/channels.py`

- [ ] **Step 1: Update `POST /api/channels/connect` to handle `target_type: "main"`**

Replace the `connect_channel` function (lines 67-99) with:

```python
@router.post("/connect")
async def connect_channel(body: ChannelConnect, ctx: AppContext = Depends(get_ctx)):
    """Connect/start a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"

    try:
        create_channel = _get_channel_factory()
        ch = create_channel(body.channel_type)

        if body.target_type == "scene":
            pool = ctx.pool
            bus = ctx.bus

            async def route(msg, scene_id=body.target_id, ct=body.channel_type):
                agent = pool.get_scene_agent(scene_id)
                if agent:
                    reply = await agent.run(msg.content)
                    await ch.send(reply, msg.user_id)
                await bus.publish("scene_message", {
                    "scene_id": scene_id,
                    "channel": ct,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })

            ch.on_message = route

        elif body.target_type == "main":
            bus = ctx.bus

            async def main_route(msg, ct=body.channel_type):
                await bus.publish("main_message", {
                    "channel": ct,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })

            ch.on_message = main_route

        ch.start(body.target_id, body.config)

        import datetime
        CHANNEL_STATUS[key] = {
            "status": "connected",
            "channel_type": body.channel_type,
            "connected_since": datetime.datetime.now().isoformat(),
            "message_count": 0,
        }
        return {"status": "connected"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/channels.py
git commit -m "feat: extend connect endpoint to support target_type=main with event bus routing"
```

---

### Task 5: Frontend TypeScript Types

**Files:**
- Modify: `web-ui/src/types/settings.ts`

- [ ] **Step 1: Add channel types to `web-ui/src/types/settings.ts`**

Replace the file content with:

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/types/settings.ts
git commit -m "feat: add ChannelTypeInfo, MainChannelInfo and related TypeScript types"
```

---

### Task 6: Channel Platform Logo Components

**Files:**
- Create: `web-ui/src/lib/channel-icons.tsx`

- [ ] **Step 1: Create `web-ui/src/lib/channel-icons.tsx`**

```tsx
/** Channel platform icons — Simple Icons for 3 platforms, hand-drawn SVG for 3. */
import { Icon, addCollection } from "@iconify/react"
import type { IconifyJSON } from "@iconify/types"
import siData from "@iconify-json/simple-icons/icons.json"
import type { SVGProps } from "react"

// Pre-register all simple-icons
addCollection(siData as unknown as IconifyJSON)

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function SiIcon(name: string, size = 18) {
  return <Icon icon={`simple-icons:${name}`} width={size} height={size} />
}

// ── Hand-drawn channel icons ──

function HandIcon({ size = 18, children, label, ...p }: IconProps & { children: React.ReactNode; label: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" role="img" aria-label={label}
         stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" {...p}>
      {children}
    </svg>
  )
}

const FeishuSvg = (p: IconProps) => (
  <HandIcon label="Feishu" {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M7 9h10M7 13h7M7 17h4" />
  </HandIcon>
)

const WeixinSvg = (p: IconProps) => (
  <HandIcon label="iLink WeChat" {...p}>
    <rect x="4" y="6" width="16" height="12" rx="3" />
    <path d="M9 11v2M12 11v2M15 11v2" strokeWidth={1.5} />
    <path d="M8 17h8" strokeWidth={1.3} />
  </HandIcon>
)

const WebApiSvg = (p: IconProps) => (
  <HandIcon label="Web API" {...p}>
    <circle cx="12" cy="5" r="3" />
    <path d="M5 19l3-7h8l3 7" />
    <path d="M7 14h10" />
  </HandIcon>
)

// ── Registry ──

export const CHANNEL_ICONS: Record<string, React.ComponentType<IconProps>> = {
  feishu: FeishuSvg,
  wechat: (p) => <>{SiIcon("wechat", p.size)}</>,
  weixin: WeixinSvg,
  telegram: (p) => <>{SiIcon("telegram", p.size)}</>,
  discord: (p) => <>{SiIcon("discord", p.size)}</>,
  web_api: WebApiSvg,
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/lib/channel-icons.tsx
git commit -m "feat: add channel platform logo components (brand icons + hand-drawn SVGs)"
```

---

### Task 7: ChannelCard Component

**Files:**
- Create: `web-ui/src/components/settings/ChannelCard.tsx`

- [ ] **Step 1: Create `web-ui/src/components/settings/ChannelCard.tsx`**

```tsx
import { Circle } from "lucide-react"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { CHANNEL_ICONS } from "@/lib/channel-icons"

interface ChannelCardProps {
  typeInfo: ChannelTypeInfo
  mainInfo?: MainChannelInfo
  onClick: () => void
}

const CAPABILITY_LABELS: Record<string, string> = {
  text: "文字", image: "图片", voice: "语音", file: "文件",
  video: "视频", card: "卡片", streaming: "流式", threads: "多线程",
  reactions: "反馈", sticker: "表情", link: "链接", post: "富文本",
  event: "事件", location: "位置",
}

const STATUS_STYLES: Record<string, { border: string; bg: string; dot: string; text: string; label: string }> = {
  connected: {
    border: "border-green-400", bg: "bg-green-50/60",
    dot: "text-green-500 fill-green-500", text: "text-green-700",
    label: "已连接",
  },
  configured: {
    border: "border-amber-400", bg: "bg-amber-50/60",
    dot: "text-amber-500 fill-amber-500", text: "text-amber-700",
    label: "已配置",
  },
  unconfigured: {
    border: "border-border", bg: "",
    dot: "text-muted-foreground/30 fill-muted-foreground/30", text: "text-muted-foreground/50",
    label: "未配置",
  },
}

export function ChannelCard({ typeInfo, mainInfo, onClick }: ChannelCardProps) {
  const IconComp = CHANNEL_ICONS[typeInfo.channel_type]
  const status = mainInfo?.status ?? "unconfigured"
  const style = STATUS_STYLES[status]

  // Collect capability tag labels
  const tags: string[] = []
  const caps = typeInfo.capabilities
  for (const key of ["text", "image", "voice", "file", "video"]) {
    if (caps.send.includes(key) || caps.receive.includes(key)) tags.push(CAPABILITY_LABELS[key])
  }
  if (caps.cards) tags.push(CAPABILITY_LABELS["card"])
  if (caps.streaming) tags.push(CAPABILITY_LABELS["streaming"])
  if (caps.threads) tags.push(CAPABILITY_LABELS["threads"])

  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all duration-200 cursor-pointer
        ${style.border} ${style.bg}
        hover:shadow-md hover:scale-[1.02]`}
    >
      <div className="size-10 flex items-center justify-center text-foreground">
        {IconComp && <IconComp size={28} />}
      </div>
      <span className="text-sm font-semibold text-foreground">{typeInfo.display_name}</span>
      <span className="text-[10px] text-muted-foreground -mt-1">{typeInfo.english_name}</span>
      <div className="flex flex-wrap justify-center gap-1 mt-1">
        {tags.map(tag => (
          <span key={tag} className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-muted text-muted-foreground">
            {tag}
          </span>
        ))}
      </div>
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${style.bg ? style.bg : 'bg-muted'} ${style.text}`}>
        <Circle className={`size-1.5 ${style.dot}`} />
        {style.label}
      </div>
    </button>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/settings/ChannelCard.tsx
git commit -m "feat: add ChannelCard component with 3-state styling and capability tags"
```

---

### Task 8: PlatformGrid Component

**Files:**
- Create: `web-ui/src/components/settings/PlatformGrid.tsx`

- [ ] **Step 1: Create `web-ui/src/components/settings/PlatformGrid.tsx`**

```tsx
import { AlertCircle, RefreshCw } from "lucide-react"
import type { ChannelTypeInfo, MainChannelInfo } from "@/types/settings"
import { ChannelCard } from "./ChannelCard"

interface PlatformGridProps {
  typeInfos: ChannelTypeInfo[]
  mainChannels: MainChannelInfo[]
  onCardClick: (typeInfo: ChannelTypeInfo, mainInfo?: MainChannelInfo) => void
  loading?: boolean
  error?: string
  onRetry?: () => void
}

export function PlatformGrid({ typeInfos, mainChannels, onCardClick, loading, error, onRetry }: PlatformGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-xl border-2 border-border h-48 animate-pulse bg-muted/50" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <AlertCircle className="size-8 text-red-400" />
        <p className="text-sm text-muted-foreground">{error}</p>
        {onRetry && (
          <button onClick={onRetry} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent transition-colors">
            <RefreshCw className="size-3" />
            重试
          </button>
        )}
      </div>
    )
  }

  if (typeInfos.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <p className="text-sm text-muted-foreground/60">暂无可用的渠道类型</p>
      </div>
    )
  }

  const channelMap = new Map(mainChannels.map(m => [m.channel_type, m]))

  return (
    <div className="grid grid-cols-3 gap-3 stagger-1">
      {typeInfos.map(ti => (
        <ChannelCard
          key={ti.channel_type}
          typeInfo={ti}
          mainInfo={channelMap.get(ti.channel_type)}
          onClick={() => onCardClick(ti, channelMap.get(ti.channel_type))}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/settings/PlatformGrid.tsx
git commit -m "feat: add PlatformGrid component with loading/error/empty states and 3-col layout"
```

---

### Task 9: ChannelDrawer Component

**Files:**
- Create: `web-ui/src/components/settings/ChannelDrawer.tsx`

- [ ] **Step 1: Create `web-ui/src/components/settings/ChannelDrawer.tsx`**

```tsx
import { useState } from "react"
import { X, Circle, Eye, EyeOff, Loader2 } from "lucide-react"
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

const CAP_LABELS: Record<string, string> = {
  text: "文字", image: "图片", voice: "语音", file: "文件", video: "视频",
  card: "卡片", sticker: "表情", link: "链接", post: "富文本", event: "事件", location: "位置",
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
          readOnly={false}
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
      onClose()
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
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
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

          {/* Status bar */}
          {status === "connected" && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-xs">
              <Circle className="size-2 text-green-500 fill-green-500" />
              <span className="font-semibold text-green-700">已连接</span>
              {mainInfo?.connected_since && (
                <span className="text-green-600/70">· {mainInfo.message_count} 条消息</span>
              )}
            </div>
          )}
          {status === "configured" && (
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
          {hasConfigFields && (
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
          {typeInfo.notes && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-700">
              {typeInfo.notes}
            </div>
          )}

          {/* Action buttons */}
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
              <button
                onClick={handleConnect}
                disabled={connecting}
                className="w-full rounded-lg bg-green-600 text-white px-4 py-2.5 text-xs font-semibold hover:bg-green-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {connecting && <Loader2 className="size-3 animate-spin" />}
                {typeInfo.channel_type === "weixin" ? "扫码连接" : "连接"}
              </button>
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
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add `slideInRight` CSS keyframe to `web-ui/src/index.css`**

Find existing `@keyframes` in index.css and add:

```css
@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/components/settings/ChannelDrawer.tsx web-ui/src/index.css
git commit -m "feat: add ChannelDrawer component with config form, status display, and action buttons"
```

---

### Task 10: Rewrite ChannelsTab with Data Fetching

**Files:**
- Rewrite: `web-ui/src/components/settings/ChannelsTab.tsx`

- [ ] **Step 1: Rewrite `web-ui/src/components/settings/ChannelsTab.tsx`**

```tsx
import { useState, useCallback } from "react"
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
  const [initialized, setInitialized] = useState(false)
  if (!initialized) {
    setInitialized(true)
    loadTypes()
    loadMain()
  }

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
      // Error shown in drawer
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
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/settings/ChannelsTab.tsx
git commit -m "feat: rewrite ChannelsTab with data fetching, platform grid, and config drawer"
```

---

### Task 11: Update SettingsModal for New ChannelsTab

**Files:**
- Modify: `web-ui/src/components/SettingsModal.tsx`

- [ ] **Step 1: Update tab 5 to use new ChannelsTab**

In `web-ui/src/components/SettingsModal.tsx`, in the `SettingsContent` function (line 43-55), change tab 5 from:

```tsx
case 5: return <ChannelsTab data={data} />
```

to:

```tsx
case 5: return <ChannelsTab />
```

And update the `onUpdate` endpoints map (lines 105-111) to remove channel entry (ChannelsTab fetches its own data now):

```tsx
const endpoints: Record<number, string> = {
  0: "/api/agents", 2: "/api/scenes", 3: "/api/skills",
  4: "/api/knowledge",
}
```

Also remove the channel endpoint from the `useEffect` fetch map (lines 67-74) — change tab 5 from `"/api/channels"` to not fetch (or let ChannelsTab handle it):

In the useEffect (lines 67-78), add a guard to skip tab 5:

```tsx
const endpoints: Record<number, string> = {
  0: "/api/agents",
  1: "/api/providers",
  2: "/api/scenes",
  3: "/api/skills",
  4: "/api/knowledge",
}
if (tab === 5) return  // ChannelsTab fetches its own data
const url = endpoints[tab]
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/components/SettingsModal.tsx
git commit -m "feat: wire new ChannelsTab into SettingsModal, skip old channel fetch"
```

---

### Task 12: Integration Verification

**Files:**
- Verify: all backend and frontend changes

- [ ] **Step 1: Run backend tests**

```bash
cd /home/leaif/Project/CocoCat && python3 -m pytest tests/test_channel.py -v
```
Expected: all 22 tests pass

- [ ] **Step 2: Verify frontend build**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npm run build 2>&1 | tail -20
```
Expected: Build succeeds with no errors

- [ ] **Step 3: Manual backend API smoke test**

```bash
# Start the app in a background terminal, then:
curl -s http://localhost:8000/api/channels/types | python3 -m json.tool | head -20
curl -s http://localhost:8000/api/channels/main | python3 -m json.tool
```
Expected: types returns 6 items, main returns 6 channels (all unconfigured)

- [ ] **Step 4: Commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: integration verification, fix any build issues"
```
