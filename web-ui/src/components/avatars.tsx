import { type SVGProps } from "react"

export interface AvatarIconDef {
  id: string
  name: string
  component: React.ComponentType<SVGProps<SVGSVGElement>>
  tags: string[]
}

function AIIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <rect x="12" y="6" width="16" height="12" rx="3" stroke="currentColor" strokeWidth="2" fill="none"/>
      <circle cx="20" cy="12" r="2" fill="currentColor"/>
      <path d="M16 22v4a2 2 0 002 2h4a2 2 0 002-2v-4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round"/>
      <path d="M20 28v6M16 34h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function CodeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M12 14l-6 6 6 6M28 14l6 6-6 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M23 10l-6 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  )
}

function StarIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 4l4.5 9.5 10.5 1.5-7.5 7.5 1.5 10L20 27l-9 5.5 1.5-10L5 15l10.5-1.5L20 4z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  )
}

function RocketIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 24s-8-4-8-12c0-4 8-8 8-8s8 4 8 8c0 8-8 12-8 12z" stroke="currentColor" strokeWidth="2"/>
      <path d="M16 18a4 4 0 118 0" stroke="currentColor" strokeWidth="2"/>
      <path d="M20 24v6M18 34h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function BoltIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M16 4l-4 16h6l-2 16 12-20h-6l4-12H16z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  )
}

function ShieldIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 4l12 6v8c0 8-5 14-12 16-7-2-12-8-12-16v-8l12-6z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M16 20l3 3 5-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function HeartIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 34s-12-8-12-16c0-5 4-8 8-8 3 0 4 2 4 2s1-2 4-2c4 0 8 3 8 8 0 8-12 16-12 16z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  )
}

function CrownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M8 30l4-20 8 8 8-8 4 20H8z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <circle cx="14" cy="20" r="2" fill="currentColor"/>
      <circle cx="20" cy="22" r="2" fill="currentColor"/>
      <circle cx="26" cy="20" r="2" fill="currentColor"/>
    </svg>
  )
}

function ZapIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2"/>
      <path d="M20 10v8h6l-6 12v-8h-6l6-12z" fill="currentColor"/>
    </svg>
  )
}

function CompassIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2"/>
      <path d="M20 14l3 9-3 3-3-9 3-3z" fill="currentColor"/>
    </svg>
  )
}

function LeafIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M32 8C24 10 18 16 14 24c-2 4-3 8-3 8s4-1 8-3c8-4 14-10 16-18l-1-1-6-2z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M14 24l-6 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function GearIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <circle cx="20" cy="20" r="6" stroke="currentColor" strokeWidth="2"/>
      <path d="M20 4v4M20 32v4M4 20h4M32 20h4M7.5 7.5l2.5 2.5M30 30l2.5 2.5M7.5 32.5l2.5-2.5M30 10l2.5-2.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function GlobeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2"/>
      <path d="M8 14h24M8 26h24M14 8c-2 4-3 8-3 12s1 8 3 12M26 8c2 4 3 8 3 12s-1 8-3 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2" fill="none"/>
    </svg>
  )
}

function BookIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M8 8h12v16H8V8z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M20 8h12v16H20V8z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M8 24v6h24v-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function DiamondIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 4l8 10-8 22-8-22 8-10z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M8 14h24" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )
}

function EyeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M20 10c-8 0-14 5-18 10 4 5 10 10 18 10s14-5 18-10c-4-5-10-10-18-10z" stroke="currentColor" strokeWidth="2"/>
      <circle cx="20" cy="20" r="4" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )
}

function FeatherIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M8 32l4-12c3-8 10-14 18-16l2 2c-2 8-8 15-16 18l-8 4v-4z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M20 20l6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function CloudIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M12 28c-4 0-6-3-5-6s3-5 7-5c0-4 4-7 8-6 3 1 5 4 5 7 3 0 5 3 4 6s-4 4-7 4H12z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  )
}

function MoonIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M28 30c-8 0-14-6-14-14 0-3 1-6 3-8-7 2-12 8-12 16 0 9 7 16 16 16 8 0 14-5 16-12-2 2-5 3-9 2z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  )
}

export const AVATAR_ICONS: AvatarIconDef[] = [
  { id: "ai", name: "AI", component: AIIcon, tags: ["tech"] },
  { id: "code", name: "Code", component: CodeIcon, tags: ["tech"] },
  { id: "star", name: "Star", component: StarIcon, tags: ["nature"] },
  { id: "rocket", name: "Rocket", component: RocketIcon, tags: ["tech"] },
  { id: "bolt", name: "Bolt", component: BoltIcon, tags: ["tech"] },
  { id: "shield", name: "Shield", component: ShieldIcon, tags: ["nature"] },
  { id: "heart", name: "Heart", component: HeartIcon, tags: ["nature"] },
  { id: "crown", name: "Crown", component: CrownIcon, tags: ["nature"] },
  { id: "zap", name: "Zap", component: ZapIcon, tags: ["tech"] },
  { id: "compass", name: "Compass", component: CompassIcon, tags: ["nature"] },
  { id: "leaf", name: "Leaf", component: LeafIcon, tags: ["nature"] },
  { id: "gear", name: "Gear", component: GearIcon, tags: ["tech"] },
  { id: "globe", name: "Globe", component: GlobeIcon, tags: ["nature"] },
  { id: "book", name: "Book", component: BookIcon, tags: ["nature"] },
  { id: "diamond", name: "Diamond", component: DiamondIcon, tags: ["nature"] },
  { id: "eye", name: "Eye", component: EyeIcon, tags: ["nature"] },
  { id: "feather", name: "Feather", component: FeatherIcon, tags: ["nature"] },
  { id: "cloud", name: "Cloud", component: CloudIcon, tags: ["nature"] },
  { id: "moon", name: "Moon", component: MoonIcon, tags: ["nature"] },
]

export const GENDER_COLORS: Record<string, { bg: string; light: string }> = {
  male: { bg: "#3B82F6", light: "#DBEAFE" },
  female: { bg: "#EC4899", light: "#FCE7F3" },
}
export const DEFAULT_COLORS = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"]
