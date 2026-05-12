# CocoCat Frontend v1 Design

## Overview

基于 paperclip 前端框架（React 19 + Vite 6 + Tailwind v4 + shadcn/ui），为 CocoCat 构建专业级管理面板，第一期覆盖 4 个页面：Dashboard、Agents、Scenes、Settings。

## Tech Stack

| Layer | Technology | Source |
|-------|-----------|--------|
| Framework | React 19 + TypeScript | paperclip |
| Build | Vite 6 | paperclip |
| Routing | react-router-dom v7 | paperclip |
| Data Fetching | @tanstack/react-query v5 | paperclip |
| Styling | Tailwind CSS v4 + OKLCH | paperclip |
| UI Components | shadcn/ui (Radix UI) | paperclip |
| Icons | lucide-react | paperclip |
| Utilities | clsx, class-variance-authority, tailwind-merge | paperclip |

## Architecture

```
web-ui/                          ← New project
├── package.json                 ← Copied from paperclip, pruned
├── vite.config.ts               ← Copied from paperclip
├── components.json              ← Copied from paperclip
├── index.html
├── tsconfig.json
└── src/
    ├── main.tsx                 ← React entry point
    ├── App.tsx                  ← Routes
    ├── index.css                ← Tailwind + theme + dark mode
    ├── components/
    │   ├── ui/                  ← 22 shadcn/ui primitives from paperclip
    │   ├── Layout.tsx           ← Sidebar + content layout
    │   └── Sidebar.tsx          ← Navigation menu
    ├── pages/
    │   ├── Dashboard.tsx
    │   ├── Agents.tsx
    │   ├── AgentDetail.tsx
    │   ├── Scenes.tsx
    │   ├── SceneDetail.tsx
    │   └── Settings.tsx
    ├── api/
    │   ├── client.ts            ← Typed HTTP client
    │   ├── agents.ts
    │   ├── scenes.ts
    │   ├── skills.ts
    │   ├── knowledge.ts
    │   ├── chat.ts
    │   └── hiring.ts
    ├── hooks/
    └── context/
        ├── ThemeContext.tsx      ← Dark/light mode
        └── ToastContext.tsx      ← Notifications
```

## Pages

### Dashboard (`/dashboard`)

Data: agents list, scenes list, pending hires, chat log.

- 4 metric cards: online agents, scene count, pending hires, recent messages
- Agent status list with online/offline indicators
- Quick links to Agents and Scenes

### Agents (`/agents`, `/agents/:id`)

List: card grid with name, role, scene, status.

Detail (tabs):
- **Profile** — read-only profile.json display
- **Skills** — skill manifest (public/private tags)
- **Memory** — MEMORY.md content
- **History** — history.jsonl entries

### Scenes (`/scenes`, `/scenes/:id`)

List: card grid with scene name, context summary, mounted KB count.

Detail:
- CONTEXT.md content display
- Mounted KBs list
- Env skills list
- Agent roster

### Settings (`/settings`)

- LLM configuration display (model, base_url — read-only)
- General info display

## API Layer

Typed client module pattern copied from paperclip `api/client.ts`:

```typescript
// api/client.ts
const BASE = "/api";
const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put, patch, delete,
};
```

Domain modules (e.g. `api/agents.ts`):
```typescript
export const agentsApi = {
  list: () => api.get<Agent[]>("/agents"),
  usage: (limit?: number) => api.get<UsageEntry[]>(`/usage?limit=${limit ?? 10}`),
};
```

## Shared Components from paperclip

All 22 shadcn/ui primitives from `paperclip/ui/src/components/ui/`:
button, card, dialog, input, textarea, select, tabs, badge, avatar, dropdown-menu, tooltip, skeleton, sheet, popover, command, table, separator, switch, label, alert, progress, scroll-area.

Business components adapted from paperclip:
- `Layout.tsx` — three-column layout (sidebar + content + optional panel)
- `Sidebar.tsx` — navigation with CocoCat menu items

## Theme

OKLCH color space with dark/light mode, copied from paperclip's `index.css`.

## Implementation Order

1. Scaffold web-ui project (Vite + React + TS + Tailwind)
2. Copy and adapt shared UI components (shadcn/ui primitives + Layout + Sidebar)
3. Create API client and domain modules
4. Build Dashboard page
5. Build Agents pages (list + detail with tabs)
6. Build Scenes pages (list + detail)
7. Build Settings page
8. Set up routing and navigation
