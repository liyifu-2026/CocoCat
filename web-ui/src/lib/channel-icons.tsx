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
