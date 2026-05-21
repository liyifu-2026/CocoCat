# CocoCat 前端交互重设计 v2 — 实现计划

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 web-ui 从多页面路由 SPA 重设计为三栏单页应用（左导航 + 中操作演示区 + 右对话区），采用 Dribbble 深蓝黑配色体系，Plus Jakarta Sans 字体，Mode 驱动动态面板。

**Architecture:** 保留现有 React + Vite 工程框架、hooks (useSessionStore, useStreaming) 和 contexts (Auth, Theme, LiveUpdates)。重写 index.css 全量 CSS 变量、Layout.tsx 改三栏骨架、App.tsx 改单页切换。新组件按功能拆分到 components/opdisplay/ 和 components/chat/。现有 pages/ 逐步废弃。

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS 4 (保留)，Lucide, cmdk, Plus Jakarta Sans (Google Fonts)

**Spec:** `docs/superpowers/specs/2026-05-21-frontend-interaction-redesign-v2.md`

---

## 文件结构概览

```
web-ui/src/
├── App.tsx                    # [重写] 三栏单页，无 routes
├── main.tsx                   # [修改] 替换 Google Fonts
├── index.css                  # [重写] 全量 CSS 变量 + 全局样式
├── index.html                 # [修改] 替换字体引用 + title
├── components/
│   ├── Layout.tsx             # [重写] 三栏骨架
│   ├── LeftNav.tsx            # [新建] 左侧 76px 图标导航
│   ├── ModeProvider.tsx       # [新建] Mode 状态 context
│   ├── OpDisplay.tsx          # [新建] 操作演示区容器
│   ├── Namecard.tsx           # [新建] Mode 驱动的名片区
│   ├── opdisplay/
│   │   ├── DefaultFunc.tsx    # [新建] default mode 功能区
│   │   ├── KbAdminFunc.tsx    # [新建] kb-admin mode 功能区
│   │   ├── Bookshelf.tsx      # [新建] 平面商城风书架
│   │   ├── ScenesView.tsx     # [新建] 场景管理视图
│   │   ├── KnowledgeView.tsx  # [新建] 知识库浏览视图
│   │   └── SettingsView.tsx   # [新建] 设置视图
│   ├── chat/
│   │   ├── ChatPanel.tsx      # [新建] 右侧对话区容器
│   │   ├── ChatMessages.tsx   # [新建] 消息流组件
│   │   └── ChatInput.tsx      # [新建] 输入框组件
│   └── viz/
│       └── VizEngine.tsx      # [新建] 操作可视化引擎
├── pages/
│   ├── Chat.tsx               # [废弃] 保留备份
│   └── Login.tsx              # [修改] 样式对齐新配色
└── hooks/                     # [保留] useSessionStore, useStreaming
```

---

## Phase 0: 准备 & 字体

### Task 0.1: 替换 Google Fonts

**Files:**
- Modify: `web-ui/index.html:10-12`

- [ ] **Step 1: 替换 index.html 字体引用和 title**

```html
<!-- 替换 line 10-12 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

Title 行改为：
```html
<title>CocoCat</title>
```

- [ ] **Step 2: 验证**

```bash
# 检查 index.html 没有残留旧字体引用
grep -n "Zen Antique\|Noto Sans" web-ui/index.html && echo "FAIL" || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/index.html
git commit -m "chore(frontend): replace fonts with Plus Jakarta Sans"
```

---

## Phase 1: CSS 体系全量重写

### Task 1.1: 重写 index.css — CSS 变量和主题

**Files:**
- Modify: `web-ui/src/index.css`

- [ ] **Step 1: 写入全新的 CSS 变量体系**

```css
@import "tailwindcss";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-ring: var(--sidebar-ring);
  --color-chart-1: var(--chart-1);
  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);
  --color-chart-4: var(--chart-4);
  --color-chart-5: var(--chart-5);
  --color-section: var(--section);
  --color-section-border: var(--section-border);
  --color-bubble: var(--bubble);
  --radius-sm: 0.375rem;
  --radius-md: 0.625rem;
  --radius-lg: 1rem;
  --radius-xl: 1.5rem;
  --font-sans: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", monospace;
}

:root {
  --background: #0d0f12;
  --foreground: #f3f4f6;
  --card: #111318;
  --card-foreground: #e2e8f0;
  --popover: #151922;
  --popover-foreground: #e2e8f0;
  --primary: #3b82f6;
  --primary-foreground: #ffffff;
  --secondary: #f59e0b;
  --muted: #1a1d24;
  --muted-foreground: #667788;
  --accent: #6366f1;
  --accent-foreground: #e2e8f0;
  --destructive: #ef4444;
  --border: rgba(255, 255, 255, 0.06);
  --input: #12151c;
  --ring: rgba(59, 130, 246, 0.3);
  --sidebar: #090a0d;
  --sidebar-foreground: #8899aa;
  --sidebar-accent: #111318;
  --sidebar-border: rgba(255, 255, 255, 0.06);
  --sidebar-ring: #3b82f6;
  --section: rgba(255, 255, 255, 0.04);
  --section-border: rgba(255, 255, 255, 0.08);
  --bubble: #151922;
  --glow-blue: rgba(59, 130, 246, 0.10);
  --glow-amber: rgba(245, 158, 11, 0.08);
  --chart-1: #3b82f6;
  --chart-2: #f59e0b;
  --chart-3: #6366f1;
  --chart-4: #22c55e;
  --chart-5: #ef4444;
}

.dark {
  --background: #0d0f12;
  --foreground: #f3f4f6;
  --card: #111318;
  --card-foreground: #e2e8f0;
  --popover: #151922;
  --popover-foreground: #e2e8f0;
  --primary: #3b82f6;
  --primary-foreground: #ffffff;
  --secondary: #f59e0b;
  --muted: #1a1d24;
  --muted-foreground: #667788;
  --accent: #6366f1;
  --accent-foreground: #e2e8f0;
  --destructive: #ef4444;
  --border: rgba(255, 255, 255, 0.06);
  --input: #12151c;
  --ring: rgba(59, 130, 246, 0.3);
  --sidebar: #090a0d;
  --sidebar-foreground: #8899aa;
  --sidebar-accent: #111318;
  --sidebar-border: rgba(255, 255, 255, 0.06);
  --sidebar-ring: #3b82f6;
  --section: rgba(255, 255, 255, 0.04);
  --section-border: rgba(255, 255, 255, 0.08);
  --bubble: #151922;
  --glow-blue: rgba(59, 130, 246, 0.10);
  --glow-amber: rgba(245, 158, 11, 0.08);
  --chart-1: #3b82f6;
  --chart-2: #f59e0b;
  --chart-3: #6366f1;
  --chart-4: #22c55e;
  --chart-5: #ef4444;
}

@layer base {
  * {
    border-color: var(--border);
    scrollbar-width: thin;
    scrollbar-color: var(--muted-foreground) transparent;
  }

  html { height: 100%; }

  body {
    background-color: var(--background);
    color: var(--foreground);
    font-family: var(--font-sans);
    height: 100%;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  #root { height: 100%; }

  ::selection {
    background: rgba(59, 130, 246, 0.3);
    color: #fff;
  }
}

/* Glow orbs */
.bg-glow-blue {
  position: fixed; top: -20%; left: -10%;
  width: 500px; height: 500px;
  background: radial-gradient(circle, var(--glow-blue) 0%, transparent 70%);
  pointer-events: none; z-index: 0; border-radius: 50%;
  filter: blur(80px);
}

.bg-glow-amber {
  position: fixed; bottom: -20%; right: -10%;
  width: 500px; height: 500px;
  background: radial-gradient(circle, var(--glow-amber) 0%, transparent 70%);
  pointer-events: none; z-index: 0; border-radius: 50%;
  filter: blur(80px);
}

/* Animations */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes messageIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

@utility stagger-1 { animation: fadeSlideUp 0.4s ease-out both; animation-delay: 0.05s; }
@utility stagger-2 { animation: fadeSlideUp 0.4s ease-out both; animation-delay: 0.12s; }
@utility stagger-3 { animation: fadeSlideUp 0.4s ease-out both; animation-delay: 0.20s; }
@utility animate-breathe { animation: breathe 1.4s ease-in-out infinite; }
@utility animate-scaleIn { animation: scaleIn 0.3s ease-out both; }

.msg-enter { animation: messageIn 0.3s ease-out both; }

/* Markdown */
.markdown-content h1 { font-size: 1.125rem; font-weight: 600; margin-top: 0.875rem; margin-bottom: 0.375rem; }
.markdown-content h2 { font-size: 1rem; font-weight: 600; margin-top: 0.75rem; margin-bottom: 0.25rem; }
.markdown-content h3 { font-size: 0.9375rem; font-weight: 600; margin-top: 0.625rem; margin-bottom: 0.25rem; }
.markdown-content p { margin-bottom: 0.5rem; }
.markdown-content p:last-child { margin-bottom: 0; }
.markdown-content ul, .markdown-content ol { padding-left: 1.25rem; margin-bottom: 0.5rem; }
.markdown-content li { margin-bottom: 0.125rem; }
.markdown-content code {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.06);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  color: #b0c4de;
}
.markdown-content pre {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  overflow-x: auto;
  margin-bottom: 0.75rem;
}
.markdown-content pre code { background: none; padding: 0; font-size: 0.75rem; color: #b0c4de; }
.markdown-content blockquote {
  border-left: 3px solid var(--primary);
  padding: 0.5rem 0.75rem;
  margin: 0.5rem 0;
  background: var(--muted);
  border-radius: 0 0.375rem 0.375rem 0;
  color: var(--muted-foreground);
}
.markdown-content table { width: 100%; border-collapse: collapse; margin-bottom: 0.5rem; font-size: 0.75rem; }
.markdown-content th, .markdown-content td {
  border: 1px solid var(--border);
  padding: 0.375rem 0.625rem;
  text-align: left;
}
.markdown-content th { background: rgba(255, 255, 255, 0.04); font-weight: 600; }
.markdown-content a { color: var(--primary); text-decoration: underline; }
.markdown-content hr { border: none; border-top: 1px solid var(--border); margin: 0.75rem 0; }
.markdown-content strong { font-weight: 600; }
.markdown-content em { font-style: italic; }

@media (prefers-reduced-motion: reduce) {
  .stagger-1, .stagger-2, .stagger-3, .msg-enter { animation: none; opacity: 1; }
}

.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }
```

- [ ] **Step 2: 确认导入路径不变**

```bash
# index.css 应该只有 @import "tailwindcss" 一行 import，确认没有其他改动
head -1 web-ui/src/index.css | grep "tailwindcss" && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/index.css
git commit -m "feat(frontend): rewrite CSS with dark blue-black theme"
```

---

## Phase 2: 三栏布局骨架

### Task 2.1: 创建 LeftNav 组件

**Files:**
- Create: `web-ui/src/components/LeftNav.tsx`

- [ ] **Step 1: 编写 LeftNav.tsx**

```tsx
import { useMode } from "@/context/ModeContext"
import { MessageSquare, Folder, BookOpen, Brain, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

interface LeftNavProps {
  active: string
  onNavigate: (nav: string) => void
}

const NAV_ITEMS = [
  { key: "chat", icon: MessageSquare, label: "Chat" },
  { key: "scenes", icon: Folder, label: "Scenes" },
  { key: "knowledge", icon: BookOpen, label: "Knowledge" },
  { key: "memory", icon: Brain, label: "Memory" },
  { key: "settings", icon: Settings, label: "Settings" },
] as const

export default function LeftNav({ active, onNavigate }: LeftNavProps) {
  return (
    <aside className="w-[76px] bg-sidebar border-r border-sidebar-border flex flex-col items-center shrink-0 py-5 gap-3.5">
      <div
        className="w-11 h-11 bg-card border border-border rounded-2xl flex items-center justify-center cursor-pointer hover:border-primary/30 transition-colors"
        onClick={() => onNavigate("chat")}
      >
        <span className="text-xs font-bold text-primary tracking-widest">CC</span>
      </div>

      <div className="w-8 h-px bg-border/50" />

      {NAV_ITEMS.map(({ key, icon: Icon, label }) => (
        <button
          key={key}
          data-label={label}
          className={cn(
            "w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 relative group",
            active === key
              ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25"
              : "text-muted-foreground hover:bg-card hover:text-foreground"
          )}
          onClick={() => onNavigate(key)}
        >
          <Icon className="size-5" />
          <span className="absolute left-14 bg-popover text-muted-foreground text-[9px] px-2 py-1 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
            {label}
          </span>
        </button>
      ))}

      <div className="mt-auto w-9 h-9 rounded-full bg-muted border-2 border-emerald-500/30 flex items-center justify-center">
        <div className="w-full h-full rounded-full bg-muted-foreground/20" />
      </div>
    </aside>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/LeftNav.tsx
git commit -m "feat(frontend): add LeftNav component with 76px icon nav"
```

### Task 2.2: 创建 ModeContext

**Files:**
- Create: `web-ui/src/context/ModeContext.tsx`

- [ ] **Step 1: 编写 ModeContext.tsx**

```tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

interface ModeInfo {
  id: string
  name: string
  description: string
}

interface ModeContextValue {
  currentMode: string
  modes: ModeInfo[]
  setMode: (mode: string) => void
}

const ModeContext = createContext<ModeContextValue>({
  currentMode: "default",
  modes: [],
  setMode: () => {},
})

export function ModeProvider({ children }: { children: ReactNode }) {
  const [currentMode, setCurrentMode] = useState("default")
  const [modes, setModes] = useState<ModeInfo[]>([
    { id: "default", name: "Coco", description: "日常助手" },
    { id: "kb-admin", name: "KB 管理", description: "知识库管理" },
  ])

  useEffect(() => {
    fetch("/api/modes")
      .then(r => r.json())
      .then((data: ModeInfo[]) => {
        if (data?.length) setModes(data)
      })
      .catch(() => {})
  }, [])

  const setMode = (mode: string) => {
    if (modes.some(m => m.id === mode)) {
      setCurrentMode(mode)
    }
  }

  return (
    <ModeContext.Provider value={{ currentMode, modes, setMode }}>
      {children}
    </ModeContext.Provider>
  )
}

export function useMode() {
  return useContext(ModeContext)
}
```

- [ ] **Step 2: 在 main.tsx 中注册 ModeProvider**

将 ModeProvider 插入到 main.tsx 的 provider 链中（在 ThemeProvider 之后、SidebarProvider 之前）：

```tsx
// main.tsx 中新增 import
import { ModeProvider } from "@/context/ModeContext"

// 在 <ThemeProvider> 之后插入 <ModeProvider>
// ...
  <ThemeProvider>
    <ModeProvider>
      <SidebarProvider>
// ...
      </SidebarProvider>
    </ModeProvider>
  </ThemeProvider>
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/context/ModeContext.tsx web-ui/src/main.tsx
git commit -m "feat(frontend): add ModeContext with dynamic mode fetching"
```

### Task 2.3: 创建 ChatInput 组件

**Files:**
- Create: `web-ui/src/components/chat/ChatInput.tsx`

- [ ] **Step 1: 编写 ChatInput.tsx**

```tsx
import { useState, useRef, useCallback } from "react"
import { Send, Plus, Loader2 } from "lucide-react"
import { useMode } from "@/context/ModeContext"

interface ChatInputProps {
  onSend: (text: string) => void
  streaming: boolean
}

export default function ChatInput({ onSend, streaming }: ChatInputProps) {
  const [input, setInput] = useState("")
  const { currentMode, modes, setMode } = useMode()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || streaming) return
    setInput("")
    onSend(text)
  }, [input, streaming, onSend])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    const cmd = value.match(/^\/mode\s+(\S+)/i)
    if (cmd?.[1] && modes.some(m => m.id === cmd[1].toLowerCase())) {
      setMode(cmd[1].toLowerCase())
      setInput("")
      return
    }
    setInput(value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-center gap-2 bg-input border border-border rounded-xl px-3 py-2 focus-within:border-primary/30 transition-colors">
        <button className="w-7 h-7 flex items-center justify-center text-muted-foreground hover:text-foreground rounded-lg transition-colors">
          <Plus className="size-4" />
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Aa"
          rows={1}
          disabled={streaming}
          className="flex-1 bg-transparent border-none outline-none resize-none text-xs text-foreground placeholder:text-muted-foreground/40 font-sans"
          onInput={(e) => {
            const el = e.currentTarget
            el.style.height = "auto"
            el.style.height = Math.min(el.scrollHeight, 120) + "px"
          }}
        />
        <button
          onClick={handleSend}
          disabled={streaming || !input.trim()}
          className="w-7 h-7 flex items-center justify-center bg-primary/15 text-primary rounded-lg hover:bg-primary/25 disabled:opacity-30 transition-colors"
        >
          {streaming ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
        </button>
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[9px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
          {currentMode}
        </span>
        <span className="text-[8px] text-muted-foreground/50">Shift+Enter to break</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/chat/ChatInput.tsx
git commit -m "feat(frontend): add ChatInput component with mode label"
```

### Task 2.4: 创建 ChatMessages 组件

**Files:**
- Create: `web-ui/src/components/chat/ChatMessages.tsx`

- [ ] **Step 1: 编写 ChatMessages.tsx**

```tsx
import { useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Loader2, ChevronRight, ChevronDown, Wrench,
  CheckCircle2, XCircle, Brain
} from "lucide-react"
import { TOOL_DISPLAY_NAMES } from "@/lib/tool-names"
import type { useStreaming } from "@/hooks/useStreaming"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  tools?: {
    id: string
    name: string
    status: "running" | "done" | "error"
    elapsed?: number
    arguments?: string
    result?: string
  }[]
  reasoningText?: string
}

interface ChatMessagesProps {
  messages: Message[]
  ctrl: ReturnType<typeof useStreaming>
}

function formatArgs(args: string | undefined): string {
  if (!args) return ""
  try {
    return JSON.stringify(JSON.parse(args), null, 0).slice(0, 200)
  } catch { return args.slice(0, 200) }
}

export default function ChatMessages({ messages, ctrl }: ChatMessagesProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, ctrl.streamText, ctrl.reasoningText])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3.5" id="chat-msgs">
      {messages.length === 0 && !ctrl.streaming && (
        <div className="flex flex-col items-center justify-center h-full text-center">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <span className="text-lg">💬</span>
          </div>
          <h2 className="text-sm font-semibold text-foreground/70 mb-1">Coco</h2>
          <p className="text-[11px] text-muted-foreground/50 max-w-[200px]">
            Your workshop operator. Type a message to begin.
          </p>
        </div>
      )}

      {messages.map((m) => (
        <div key={m.id} className={`flex msg-enter ${m.role === "user" ? "justify-end" : "justify-start"}`}>
          <div className={`max-w-[85%] space-y-1.5 ${m.role === "user" ? "" : "w-full max-w-[85%]"}`}>
            {m.role === "assistant" && m.reasoningText && (
              <details className="rounded-xl border border-accent/15 bg-accent/5 overflow-hidden">
                <summary className="flex items-center gap-2 px-4 py-2 text-[10px] font-medium text-accent cursor-pointer">
                  <Brain className="size-3" />
                  思考过程
                </summary>
                <div className="px-4 pb-3 text-[10px] text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto">{m.reasoningText}</div>
              </details>
            )}
            {m.role === "assistant" && m.tools && m.tools.length > 0 && (
              <details className="rounded-xl border border-border bg-card/50 overflow-hidden">
                <summary className="flex items-center gap-2 px-4 py-2 text-[10px] font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
                  <Wrench className="size-3 text-blue-500" />
                  工具调用 ({m.tools.length})
                </summary>
                <div className="px-4 pb-3 space-y-1">
                  {m.tools.map(tc => (
                    <div key={tc.id} className="flex items-start gap-2 rounded-lg bg-accent/10 px-3 py-1.5 text-[10px]">
                      <div className="mt-0.5 shrink-0">
                        {tc.status === "done" && <CheckCircle2 className="size-3 text-green-500" />}
                        {tc.status === "error" && <XCircle className="size-3 text-red-500" />}
                        {tc.status === "running" && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-foreground/70">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                        {tc.elapsed !== undefined && <span className="text-muted-foreground/50 ml-1">{tc.elapsed}s</span>}
                        {tc.arguments && <div className="text-muted-foreground/50 font-mono text-[9px] mt-0.5 break-all">{formatArgs(tc.arguments)}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
            <div className={`text-[11px] leading-relaxed px-4 py-2.5 ${
              m.role === "user"
                ? "bg-primary text-primary-foreground rounded-2xl rounded-br-md"
                : "bg-bubble text-foreground/85 rounded-2xl rounded-bl-md border border-border"
            }`}>
              <div className="markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      ))}

      {ctrl.streaming && (
        <div className="flex justify-start">
          <div className="max-w-[85%] space-y-2 w-full">
            {ctrl.reasoningText && (
              <div className="rounded-xl border border-accent/20 bg-card p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="size-3.5 text-accent" />
                  <span className="text-[10px] font-medium">思考中</span>
                  <Loader2 className="size-3 text-accent animate-spin" />
                </div>
                <div className="text-[10px] text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto">{ctrl.reasoningText}</div>
              </div>
            )}

            {ctrl.toolCalls.length > 0 && (
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <button
                  onClick={() => ctrl.setToolsCollapsed(!ctrl.toolsCollapsed)}
                  className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-accent/10 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Wrench className="size-3.5 text-blue-500" />
                    <span className="text-[10px] font-medium">工具调用</span>
                    <span className="text-[9px] text-muted-foreground">{ctrl.toolCalls.length}</span>
                    {ctrl.streaming && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                  </div>
                  {ctrl.toolsCollapsed ? <ChevronRight className="size-4 text-muted-foreground" /> : <ChevronDown className="size-4 text-muted-foreground" />}
                </button>
                {!ctrl.toolsCollapsed && (
                  <div className="px-4 pb-3 space-y-1">
                    {ctrl.toolCalls.map(tc => (
                      <div key={tc.id} className="flex items-start gap-2 rounded-lg bg-accent/10 px-3 py-2 text-[10px]">
                        <div className="mt-0.5 shrink-0">
                          {tc.status === "running" && <Loader2 className="size-3 text-blue-500 animate-spin" />}
                          {tc.status === "done" && <CheckCircle2 className="size-3 text-green-500" />}
                          {tc.status === "error" && <XCircle className="size-3 text-red-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="font-medium">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                          {tc.elapsed !== undefined && <span className="text-muted-foreground ml-1">{tc.elapsed}s</span>}
                          <span className={`text-[9px] ml-2 px-1.5 py-0.5 rounded-full ${
                            tc.status === "running" ? "bg-blue-500/10 text-blue-400" :
                            tc.status === "done" ? "bg-green-500/10 text-green-400" :
                            "bg-red-500/10 text-red-400"
                          }`}>{tc.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="bg-bubble border border-border rounded-2xl rounded-bl-md px-4 py-3">
              {ctrl.streamText ? (
                <div className="markdown-content text-[11px]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{ctrl.streamText}</ReactMarkdown>
                </div>
              ) : (
                <span className="inline-flex gap-1">
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.15s" }} />
                  <span className="size-2 rounded-full bg-muted-foreground/30 animate-breathe" style={{ animationDelay: "0.3s" }} />
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/chat/ChatMessages.tsx
git commit -m "feat(frontend): add ChatMessages component"
```

### Task 2.5: 创建 ChatPanel 容器

**Files:**
- Create: `web-ui/src/components/chat/ChatPanel.tsx`

- [ ] **Step 1: 编写 ChatPanel.tsx**

```tsx
import { useCallback, useRef, useEffect } from "react"
import { useSessionStore } from "@/hooks/useSessionStore"
import { useStreaming } from "@/hooks/useStreaming"
import { useMode } from "@/context/ModeContext"
import ChatMessages from "./ChatMessages"
import ChatInput from "./ChatInput"

export default function ChatPanel() {
  const store = useSessionStore("")
  const currentIdRef = useRef(store.currentId)
  currentIdRef.current = store.currentId
  const ctrl = useStreaming(currentIdRef)
  const { currentMode, setMode } = useMode()
  const skipClearUntilId = useRef<string | null>(null)

  useEffect(() => {
    if (!store.currentId) return
    fetch(`/api/chat/history?session_id=${store.currentId}`)
      .then(r => r.json())
      .then(d => {
        if (!d.messages?.length) return
        if (d.messages.length > store.messages.length) {
          store.clearMessages()
          d.messages.forEach((m: any) => {
            if (m.role === "user") store.addUserMessage(m.content)
            else store.addAssistantMessage(m.content)
          })
        }
      })
      .catch(() => {})
  }, [store.currentId])

  useEffect(() => {
    if (skipClearUntilId.current === store.currentId) {
      skipClearUntilId.current = null
      return
    }
    if (!ctrl.streaming) ctrl.clear()
  }, [store.currentId, ctrl.streaming])

  const sendMessage = useCallback(async (userMsg: string) => {
    if (ctrl.streaming) return
    if (!store.currentId) {
      const sid = store.createSession(userMsg.slice(0, 30))
      currentIdRef.current = sid
    }
    store.addUserMessage(userMsg)
    ctrl.start()

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: userMsg,
          user_id: "local",
          session_id: currentIdRef.current || undefined,
          mode: currentMode,
        }),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      const reply = data.reply || "(no response)"
      if (data.mode_switch) setMode(data.mode_switch)
      const snap = ctrl.snapshot()
      store.addAssistantMessage(reply, snap)
    } catch (e) {
      store.addAssistantMessage("Error: " + String(e))
    }
    ctrl.complete()
  }, [store, ctrl, currentMode])

  return (
    <div className="w-[380px] bg-sidebar border-l border-sidebar-border flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-sidebar-border flex items-center gap-2.5">
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
        <span className="text-xs font-semibold text-foreground">Coco</span>
        <span className="text-[9px] px-2 py-0.5 rounded-full bg-primary/12 text-primary font-medium">{currentMode}</span>
      </div>

      <ChatMessages messages={store.messages} ctrl={ctrl} />

      <ChatInput onSend={sendMessage} streaming={ctrl.streaming} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/chat/ChatPanel.tsx
git commit -m "feat(frontend): add ChatPanel container"
```

### Task 2.6: 创建 Namecard 组件

**Files:**
- Create: `web-ui/src/components/Namecard.tsx`

- [ ] **Step 1: 编写 Namecard.tsx**

```tsx
import { useState } from "react"
import { useMode } from "@/context/ModeContext"
import { cn } from "@/lib/utils"

const MODE_STYLES: Record<string, { icon: string; title: string; subtitle: string; status: string; gradient: string }> = {
  default: {
    icon: "💬",
    title: "Coco",
    subtitle: "Workshop Operator",
    status: "\"Hello! 12 tools ready.\"",
    gradient: "bg-gradient-to-b from-blue-500/10 to-transparent",
  },
  "kb-admin": {
    icon: "📚",
    title: "Coco · KB Admin",
    subtitle: "Knowledge Base Operator",
    status: "\"3 KB active. Tools ready.\"",
    gradient: "bg-gradient-to-b from-amber-500/10 to-transparent",
  },
}

export default function Namecard() {
  const { currentMode, modes, setMode } = useMode()
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const style = MODE_STYLES[currentMode] || MODE_STYLES.default

  return (
    <div className={cn("px-6 py-6 text-center border-b border-border flex-shrink-0 relative", style.gradient)}>
      <div className={cn(
        "w-14 h-14 mx-auto mb-2.5 rounded-full flex items-center justify-center text-2xl border-2",
        currentMode === "kb-admin" ? "bg-amber-500/10 border-amber-500/25" : "bg-blue-500/10 border-blue-500/25"
      )}>
        {style.icon}
      </div>

      <h2 className="text-[15px] font-semibold text-foreground">{style.title}</h2>
      <p className="text-[10px] text-muted-foreground mt-0.5">{style.subtitle}</p>

      <div className="relative inline-block mt-2">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className={cn(
            "text-[10px] px-3 py-1 rounded-full font-medium cursor-pointer transition-colors",
            currentMode === "kb-admin"
              ? "bg-amber-500/12 text-amber-400"
              : "bg-primary/12 text-primary"
          )}
        >
          {currentMode} ▾
        </button>

        {dropdownOpen && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 bg-popover border border-border rounded-lg py-1 shadow-lg z-20 min-w-[130px]">
            {modes.map(m => (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setDropdownOpen(false) }}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[10px] rounded-md transition-colors",
                  m.id === currentMode ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-card"
                )}
              >
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground/70 italic mt-1.5">{style.status}</p>

      {dropdownOpen && <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/Namecard.tsx
git commit -m "feat(frontend): add mode-driven Namecard component"
```

### Task 2.7: 创建 DefaultFunc 组件

**Files:**
- Create: `web-ui/src/components/opdisplay/DefaultFunc.tsx`

- [ ] **Step 1: 编写 DefaultFunc.tsx**

```tsx
import { useSessionStore } from "@/hooks/useSessionStore"
import { cn } from "@/lib/utils"

export default function DefaultFunc() {
  const store = useSessionStore("")

  return (
    <div className="flex flex-col gap-2.5 p-4">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2.5">📋 Sessions</div>
        <button
          className="w-full border border-dashed border-border rounded-lg text-center py-2 text-[10px] text-muted-foreground/60 hover:border-primary/30 hover:text-muted-foreground transition-colors mb-2"
          onClick={() => store.newSession()}
        >
          + New Session
        </button>
        {[...store.sessions].sort((a, b) => b.createdAt - a.createdAt).slice(0, 5).map(s => (
          <div
            key={s.id}
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 rounded-md text-[10px] cursor-pointer transition-colors",
              s.id === store.currentId ? "bg-primary/8 text-foreground" : "text-muted-foreground hover:bg-card/50"
            )}
            onClick={() => store.selectSession(s.id)}
          >
            <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", s.id === store.currentId ? "bg-primary" : "bg-muted-foreground/30")} />
            <span className="truncate flex-1">{s.title || "Untitled"}</span>
            <span className="text-[9px] text-muted-foreground/50 shrink-0">
              {timeAgo(s.createdAt)}
            </span>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2">🔧 Quick Actions</div>
        <div className="flex flex-wrap gap-1.5">
          {["分析当前项目", "创建新任务", "今日摘要", "清理记忆"].map(action => (
            <span key={action} className="inline-block bg-muted/50 border border-border rounded-full px-2.5 py-1 text-[9px] text-muted-foreground cursor-pointer hover:bg-muted hover:text-foreground transition-colors">
              {action}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/opdisplay/DefaultFunc.tsx
git commit -m "feat(frontend): add DefaultFunc component"
```

---

## Phase 3: OpDisplay 容器 + App 重写

### Task 3.1: 创建 OpDisplay 容器

**Files:**
- Create: `web-ui/src/components/OpDisplay.tsx`

- [ ] **Step 1: 编写 OpDisplay.tsx**

```tsx
import { useMode } from "@/context/ModeContext"
import Namecard from "./Namecard"
import DefaultFunc from "./opdisplay/DefaultFunc"
import KbAdminFunc from "./opdisplay/KbAdminFunc"
import ScenesView from "./opdisplay/ScenesView"
import KnowledgeView from "./opdisplay/KnowledgeView"
import SettingsView from "./opdisplay/SettingsView"

interface OpDisplayProps {
  activeNav: string
}

export default function OpDisplay({ activeNav }: OpDisplayProps) {
  const { currentMode } = useMode()

  const renderFunc = () => {
    if (activeNav === "chat") {
      return currentMode === "kb-admin" ? <KbAdminFunc /> : <DefaultFunc />
    }
    switch (activeNav) {
      case "scenes": return <ScenesView />
      case "knowledge": return <KnowledgeView />
      case "settings": return <SettingsView />
      case "memory": return (
        <div className="p-4">
          <div className="bg-card border border-border rounded-xl p-3">
            <div className="text-[10px] font-semibold text-muted-foreground">🧠 Memory Timeline</div>
          </div>
        </div>
      )
      default: return <DefaultFunc />
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      <Namecard />
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {renderFunc()}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/OpDisplay.tsx
git commit -m "feat(frontend): add OpDisplay container with mode-driven routing"
```

### Task 3.2: 创建占位视图组件

**Files:**
- Create: `web-ui/src/components/opdisplay/ScenesView.tsx`
- Create: `web-ui/src/components/opdisplay/KnowledgeView.tsx`
- Create: `web-ui/src/components/opdisplay/SettingsView.tsx`

- [ ] **Step 1: 编写 ScenesView.tsx**

```tsx
export default function ScenesView() {
  return (
    <div className="p-4 space-y-2.5">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2">📁 Scenes</div>
        <p className="text-[10px] text-muted-foreground/50">Scene management — coming soon.</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 编写 KnowledgeView.tsx**

```tsx
export default function KnowledgeView() {
  return (
    <div className="p-4 space-y-2.5">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-2">📚 Knowledge Base</div>
        <p className="text-[10px] text-muted-foreground/50">Knowledge browser — coming soon.</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 编写 SettingsView.tsx**

```tsx
import { useTheme } from "@/context/ThemeContext"
import { useLang } from "@/context/LanguageContext"

export default function SettingsView() {
  const { theme, toggleTheme } = useTheme()
  const { lang, setLang } = useLang()

  return (
    <div className="p-4 space-y-2.5">
      <div className="bg-card border border-border rounded-xl p-3">
        <div className="text-[10px] font-semibold text-muted-foreground mb-3">⚙ Settings</div>
        <div className="space-y-2">
          <div className="flex items-center justify-between py-1.5">
            <span className="text-[10px] text-foreground">Theme</span>
            <button
              onClick={toggleTheme}
              className="text-[9px] px-2.5 py-1 rounded-full bg-muted border border-border text-muted-foreground"
            >
              {theme === "dark" ? "🌙 Dark" : "☀️ Light"}
            </button>
          </div>
          <div className="flex items-center justify-between py-1.5">
            <span className="text-[10px] text-foreground">Language</span>
            <select
              value={lang}
              onChange={e => setLang(e.target.value as "en" | "zh")}
              className="text-[9px] px-2 py-1 rounded-full bg-muted border border-border text-muted-foreground outline-none"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/components/opdisplay/ScenesView.tsx web-ui/src/components/opdisplay/KnowledgeView.tsx web-ui/src/components/opdisplay/SettingsView.tsx
git commit -m "feat(frontend): add placeholder views for Scenes, Knowledge, Settings"
```

### Task 3.3: 重写 Layout.tsx — 三栏骨架

**Files:**
- Modify: `web-ui/src/components/Layout.tsx`

- [ ] **Step 1: 改写 Layout.tsx**

```tsx
import { useState } from "react"
import { Outlet } from "react-router-dom"
import LeftNav from "./LeftNav"
import OpDisplay from "./OpDisplay"
import ChatPanel from "./chat/ChatPanel"

export default function Layout() {
  const [activeNav, setActiveNav] = useState("chat")

  return (
    <div className="flex h-screen relative">
      <div className="bg-glow-blue" />
      <div className="bg-glow-amber" />

      <LeftNav active={activeNav} onNavigate={setActiveNav} />

      {activeNav === "chat" ? (
        <>
          <OpDisplay activeNav={activeNav} />
          <ChatPanel />
        </>
      ) : (
        <OpDisplay activeNav={activeNav} />
      )}

      <Outlet />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/Layout.tsx
git commit -m "feat(frontend): rewrite Layout as three-column skeleton"
```

### Task 3.4: 重写 App.tsx — 简化路由

**Files:**
- Modify: `web-ui/src/App.tsx`

- [ ] **Step 1: 改写 App.tsx**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import ErrorBoundary from "@/components/ErrorBoundary"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/*" element={<ErrorBoundary><div /></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: 更新 Login 页样式**

修改 `web-ui/src/pages/Login.tsx`，将背景色和输入框颜色对齐新主题（替换 `bg-background` 等 class 以匹配新 CSS 变量）。

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/App.tsx web-ui/src/pages/Login.tsx
git commit -m "feat(frontend): simplify App routing to single-page three-column"
```

---

## Phase 4: KB-Admin 模式和书架

### Task 4.1: 创建 Bookshelf 组件

**Files:**
- Create: `web-ui/src/components/opdisplay/Bookshelf.tsx`

- [ ] **Step 1: 编写 Bookshelf.tsx**

```tsx
import { cn } from "@/lib/utils"

interface Book {
  id: string
  title: string
  category: string
  cover: string
  editing?: boolean
}

interface BookshelfProps {
  books?: Book[]
  categories?: string[]
}

const COVER_COLORS = [
  "bg-gradient-to-br from-blue-600 to-blue-800",
  "bg-gradient-to-br from-indigo-600 to-indigo-800",
  "bg-gradient-to-br from-cyan-600 to-cyan-800",
  "bg-gradient-to-br from-amber-600 to-amber-800",
  "bg-gradient-to-br from-rose-600 to-rose-800",
  "bg-gradient-to-br from-emerald-600 to-emerald-800",
  "bg-gradient-to-br from-violet-600 to-violet-800",
  "bg-gradient-to-br from-sky-600 to-sky-800",
]

const DEMO_BOOKS: Record<string, Book[]> = {
  "Project Docs": [
    { id: "1", title: "Backend API", category: "Project Docs", cover: COVER_COLORS[0] },
    { id: "2", title: "Frontend UI", category: "Project Docs", cover: COVER_COLORS[1] },
    { id: "3", title: "Deployment", category: "Project Docs", cover: COVER_COLORS[2] },
    { id: "4", title: "DB Schema", category: "Project Docs", cover: COVER_COLORS[3] },
  ],
  "Wiki": [
    { id: "5", title: "架构总览", category: "Wiki", cover: COVER_COLORS[4] },
    { id: "6", title: "API 设计", category: "Wiki", cover: COVER_COLORS[5] },
    { id: "7", title: "测试指南", category: "Wiki", cover: COVER_COLORS[6] },
    { id: "8", title: "贡献指南", category: "Wiki", cover: COVER_COLORS[7] },
  ],
}

export default function Bookshelf() {
  const categories = Object.entries(DEMO_BOOKS)

  return (
    <div className="p-4 space-y-4">
      {categories.map(([cat, books]) => (
        <div key={cat} className="bg-card border border-border rounded-xl p-3">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-semibold text-amber-400">📁 {cat}</span>
            <span className="text-[9px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full">{books.length} books</span>
          </div>

          <div className="grid grid-cols-4 gap-3">
            {books.map(book => (
              <div
                key={book.id}
                className={cn(
                  "group cursor-pointer transition-all duration-200 hover:-translate-y-1",
                  book.editing && "animate-pulse"
                )}
              >
                <div className={cn(
                  "aspect-[3/4] rounded-lg flex items-center justify-center text-[9px] font-medium text-white text-center leading-tight p-2 relative",
                  book.cover
                )}>
                  {book.title}
                  {book.editing && (
                    <span className="absolute top-1 right-1 text-[8px]">✏️</span>
                  )}
                </div>
                <p className="text-[8px] text-muted-foreground mt-1.5 text-center truncate">{book.title}</p>
              </div>
            ))}
            <div className="aspect-[3/4] rounded-lg border border-dashed border-border flex items-center justify-center cursor-pointer hover:border-amber-500/30 transition-colors">
              <span className="text-muted-foreground/40 text-lg">+</span>
            </div>
          </div>
        </div>
      ))}

      <div className="border border-dashed border-border rounded-lg py-2.5 text-center text-[9px] text-muted-foreground/50 cursor-pointer hover:border-amber-500/20 hover:text-amber-400 transition-colors">
        + Add New Category Shelf
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/opdisplay/Bookshelf.tsx
git commit -m "feat(frontend): add visual Bookshelf component"
```

### Task 4.2: 创建 KbAdminFunc 组件

**Files:**
- Create: `web-ui/src/components/opdisplay/KbAdminFunc.tsx`

- [ ] **Step 1: 编写 KbAdminFunc.tsx**

```tsx
import Bookshelf from "./Bookshelf"

export default function KbAdminFunc() {
  return (
    <div className="flex flex-col">
      <Bookshelf />

      <div className="px-4 pb-4 space-y-2.5">
        <div className="bg-card border border-accent/12 rounded-xl p-3">
          <div className="text-[10px] font-semibold text-accent mb-2">⚡ Live Operations</div>
          <div className="space-y-1">
            <OpRow icon="⏳" text="Reading backend-api.md..." color="text-foreground/80" />
            <OpRow icon="✓" text="Updated Architecture wiki" />
            <OpRow icon="✓" text="Created API Design entry" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-3">
          <div className="text-[10px] font-semibold text-muted-foreground mb-2">🔧 KB Actions</div>
          <div className="flex flex-wrap gap-1.5">
            {["上传文档", "创建 Wiki", "查重/去重", "全文检索", "导出"].map(a => (
              <span key={a} className="inline-block bg-muted/50 border border-border rounded-full px-2.5 py-1 text-[9px] text-muted-foreground cursor-pointer hover:bg-muted hover:text-foreground transition-colors">
                {a}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function OpRow({ icon, text, color = "text-muted-foreground/60" }: { icon: string; text: string; color?: string }) {
  return (
    <div className={`flex items-center gap-2 text-[9px] ${color}`}>
      <span className="text-[10px]">{icon}</span>
      <span>{text}</span>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/components/opdisplay/KbAdminFunc.tsx
git commit -m "feat(frontend): add KbAdminFunc with bookshelf + live ops"
```

---

## Phase 5: 操作可视化引擎

> **后端依赖**：VizEngine 监听 `tool_event` WebSocket 事件，该事件类型需后端在 chat stream 中新增推送。在 `tool_event` 可用前，VizEngine 不会崩溃，仅不显示实时内容。

### Task 5.1: 创建 VizEngine 组件

**Files:**
- Create: `web-ui/src/components/viz/VizEngine.tsx`

- [ ] **Step 1: 编写 VizEngine.tsx**

```tsx
import { useState, useEffect } from "react"
import { useLiveUpdates } from "@/context/LiveUpdatesContext"

type VizState = "idle" | "active"

interface VizEvent {
  tool: string
  args: Record<string, unknown>
  status: "start" | "delta" | "end"
  data?: unknown
}

export default function VizEngine() {
  const [state, setState] = useState<VizState>("idle")
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const [output, setOutput] = useState<string>("")
  const { onMessage } = useLiveUpdates()

  useEffect(() => {
    const unsub = onMessage("tool_event", (data: Record<string, unknown>) => {
      const event = data as unknown as VizEvent

      switch (event.status) {
        case "start":
          setState("active")
          setCurrentTool(event.tool)
          setOutput("")
          break
        case "delta":
          if (typeof event.data === "string") {
            setOutput(prev => prev + event.data)
          }
          break
        case "end":
          // Keep visible for 3s, then return to idle
          setTimeout(() => {
            setState("idle")
            setCurrentTool(null)
          }, 3000)
          break
      }
    })

    return unsub
  }, [onMessage])

  if (state === "idle") return null

  return (
    <div className="px-4 pb-3">
      <div className="bg-card border border-accent/20 rounded-xl p-3 animate-scaleIn">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-accent animate-breathe" />
          <span className="text-[10px] font-medium text-accent">
            {currentTool || "Working"} · live
          </span>
        </div>
        {output && (
          <pre className="text-[10px] text-muted-foreground font-mono max-h-40 overflow-y-auto whitespace-pre-wrap">
            {output}
          </pre>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 在 OpDisplay 中集成 VizEngine**

在 `OpDisplay.tsx` 中的 Namecard 和 Func 区之间插入 `<VizEngine />`。

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/components/viz/VizEngine.tsx
git commit -m "feat(frontend): add VizEngine for real-time operation visualization"
```

---

## Phase 6: 清理和验证

### Task 6.1: 验证构建

- [ ] **Step 1: 检查 TypeScript 编译**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | head -30
```

修复所有类型错误。

- [ ] **Step 2: 检查 Vite 构建**

```bash
cd web-ui && npm run build 2>&1 | tail -20
```

确认构建成功无报错。

- [ ] **Step 3: Commit**

```bash
git add -A web-ui/src/
git commit -m "fix(frontend): resolve TypeScript and build errors"
```

---

## 实现顺序

```
Phase 0 → Phase 1 → Phase 2 (Task 2.1→2.2→2.3→2.4→2.5→2.6→2.7)
  → Phase 3 (Task 3.1→3.2→3.3→3.4)
  → Phase 4 (Task 4.1→4.2)
  → Phase 5
  → Phase 6
```
