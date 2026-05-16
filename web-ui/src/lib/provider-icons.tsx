/** LLM provider icons — @iconify-json/simple-icons for 10 providers, hand-drawn for 5. */
import type { SVGProps } from "react"
import { Icon, addCollection } from "@iconify/react"
import type { IconifyJSON } from "@iconify/types"
import siData from "@iconify-json/simple-icons/icons.json"

// Pre-register all simple-icons (3700+) so <Icon> works offline
addCollection(siData as unknown as IconifyJSON)

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function SiIcon(name: string, size = 18) {
  return <Icon icon={`simple-icons:${name}`} width={size} height={size} />
}

// ── Hand-drawn fallbacks (5 providers not in simple-icons) ──

function HandIcon({ size = 18, children, label, ...p }: IconProps & { children: React.ReactNode; label: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" role="img" aria-label={label} stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" {...p}>
      {children}
    </svg>
  )
}

const GroqSvg = (p: IconProps) => (
  <HandIcon label="Groq" {...p}>
    <path d="M5 7l4 4v6l3-3 3 3v-6l4-4" strokeLinejoin="round"/>
    <circle cx="12" cy="7" r="2" fill="currentColor" opacity={0.2} strokeWidth={1.2}/>
  </HandIcon>
)

const SiliconFlowSvg = (p: IconProps) => (
  <HandIcon label="SiliconFlow" {...p}>
    <path d="M6 12h12"/>
    <path d="M9 8l-3 4 3 4M15 8l3 4-3 4"/>
  </HandIcon>
)

const ZhipuSvg = (p: IconProps) => (
  <HandIcon label="ZhipuAI" {...p}>
    <rect x="4" y="5" width="6" height="6" rx="1.5"/>
    <rect x="14" y="5" width="6" height="6" rx="1.5"/>
    <rect x="9" y="14" width="6" height="5" rx="1.5"/>
    <path d="M7 11v3M17 11v3" strokeWidth={1.3}/>
  </HandIcon>
)

const DashScopeSvg = (p: IconProps) => (
  <HandIcon label="DashScope" {...p}>
    <circle cx="12" cy="12" r="8"/>
    <circle cx="8" cy="10" r="2" fill="currentColor" opacity={0.2} strokeWidth={1.2}/>
    <circle cx="14" cy="14" r="2" fill="currentColor" opacity={0.2} strokeWidth={1.2}/>
    <path d="M9.5 10.5l3.5 3.5" strokeWidth={1.3}/>
  </HandIcon>
)

const VolcengineSvg = (p: IconProps) => (
  <HandIcon label="Volcengine" {...p}>
    <path d="M12 3v18M3 12h18" strokeWidth={1.3} opacity={0.2}/>
    <circle cx="12" cy="12" r="6"/>
    <circle cx="12" cy="12" r="2" fill="currentColor" opacity={0.15}/>
  </HandIcon>
)

// ── Registry ──

export const PROVIDER_ICONS: Record<string, React.ComponentType<IconProps>> = {
  openai:      (p) => <>{SiIcon("openai", p.size)}</>,
  deepseek:    (p) => <>{SiIcon("deepseek", p.size)}</>,
  anthropic:   (p) => <>{SiIcon("anthropic", p.size)}</>,
  ollama:      (p) => <>{SiIcon("ollama", p.size)}</>,
  gemini:      (p) => <>{SiIcon("googlegemini", p.size)}</>,
  openrouter:  (p) => <>{SiIcon("openrouter", p.size)}</>,
  minimax:     (p) => <>{SiIcon("minimax", p.size)}</>,
  dashscope:   (p) => <>{SiIcon("qwen", p.size)}</>,
  mistral:     (p) => <>{SiIcon("mistralai", p.size)}</>,
  moonshot:    (p) => <>{SiIcon("moonshotai", p.size)}</>,
  groq:        GroqSvg,
  siliconflow: SiliconFlowSvg,
  zhipu:       ZhipuSvg,
  volcengine:  VolcengineSvg,
}
